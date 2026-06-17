from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import BooleanField, Case, F, Q, When
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Annonce, AnnonceImage, SellerVerification, BazarFavori
from .forms import AnnonceForm

# ── Constantes ─────────────────────────────────────────────────────────────────
PAGE_SIZE       = 12
MAX_IMAGES      = 8           # vendeur standard
MAX_IMAGES_VERIFIED = 12      # vendeur vérifié
BUMP_COOLDOWN_H = 24          # heures entre deux bumps


# ── Liste / Explore ─────────────────────────────────────────────────────────────

def bazar_index(request):
    """
    Page principale du Bazar : liste des annonces actives avec filtres.
    URL: /bazar/
    """
    qs = (
        Annonce.objects
        .filter(status='active')
        .select_related('seller', 'seller__seller_verification')
        .prefetch_related('images')
        # Annotation booléenne : le vendeur est-il vérifié ?
        .annotate(
            seller_verified=Case(
                When(seller__seller_verification__status='approved', then=True),
                default=False,
                output_field=BooleanField(),
            )
        )
    )

    # ── Filtres URL ──────────────────────────────────────────────────────────
    q            = request.GET.get('q', '').strip()
    category     = request.GET.get('cat', '').strip()
    condition    = request.GET.get('cond', '').strip()
    location     = request.GET.get('loc', '').strip()
    region       = request.GET.get('region', '').strip()
    price_min    = request.GET.get('pmin', '').strip()
    price_max    = request.GET.get('pmax', '').strip()
    sort         = request.GET.get('sort', 'recent')
    only_verified = request.GET.get('verified', '')

    if q:
        qs = qs.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(location__icontains=q)
        )

    if category:
        qs = qs.filter(category=category)

    if condition:
        qs = qs.filter(condition=condition)

    if location:
        qs = qs.filter(location__icontains=location)

    if region:
        qs = qs.filter(region=region)

    if price_min:
        try:
            qs = qs.filter(Q(price__gte=int(price_min)) | Q(price__isnull=True))
        except ValueError:
            pass

    if price_max:
        try:
            qs = qs.filter(price__lte=int(price_max))
        except ValueError:
            pass

    # Filtre vendeurs vérifiés
    if only_verified:
        qs = qs.filter(seller_verified=True)

    # Tri — les vendeurs vérifiés sont toujours boostés en tête.
    # Pour 'recent', les annonces bumpées remontent (bumped_at > created_at).
    if sort == 'price_asc':
        qs = qs.order_by('-seller_verified', 'price', F('bumped_at').desc(nulls_last=True), '-created_at')
    elif sort == 'price_desc':
        qs = qs.order_by('-seller_verified', '-price', F('bumped_at').desc(nulls_last=True), '-created_at')
    elif sort == 'popular':
        qs = qs.order_by('-seller_verified', '-views_count', F('bumped_at').desc(nulls_last=True), '-created_at')
    else:
        # Par défaut : bumped_at desc (null en dernier), puis created_at desc
        qs = qs.order_by('-seller_verified', F('bumped_at').desc(nulls_last=True), '-created_at')

    # ── Pagination ────────────────────────────────────────────────────────────
    paginator = Paginator(qs, PAGE_SIZE)
    page_obj  = paginator.get_page(request.GET.get('page'))

    from regions import REGION_CHOICES, REGION_LABELS
    # Région courante de l'utilisateur (pour pré-sélectionner "Ma région")
    user_region = ''
    if request.user.is_authenticated:
        user_region = getattr(request.user, 'region', '') or ''

    context = {
        'page_obj':        page_obj,
        'categories':      Annonce.CATEGORY_CHOICES,
        'conditions':      Annonce.CONDITION_CHOICES,
        'q':               q,
        'sel_cat':         category,
        'sel_cond':        condition,
        'sel_loc':         location,
        'sel_region':      region,
        'sel_pmin':        price_min,
        'sel_pmax':        price_max,
        'sort':            sort,
        'only_verified':   only_verified,
        'total':           paginator.count,
        'region_choices':  REGION_CHOICES,
        'user_region':     user_region,
        'user_region_label': REGION_LABELS.get(user_region, ''),
    }
    return render(request, 'bazar/index.html', context)


# ── Détail d'une annonce ────────────────────────────────────────────────────────

def annonce_detail(request, pk):
    """
    Page de détail d'une annonce.
    URL: /bazar/<pk>/
    """
    annonce = get_object_or_404(
        Annonce.objects
        .select_related('seller', 'seller__seller_verification')
        .prefetch_related('images'),
        pk=pk,
    )

    # Incrémenter le compteur de vues (pas pour le vendeur lui-même)
    if request.user != annonce.seller:
        annonce.increment_views()

    # Annonces similaires (même catégorie, actives, pas la même)
    similaires = (
        Annonce.objects.filter(category=annonce.category, status='active')
        .exclude(pk=annonce.pk)
        .select_related('seller')
        .prefetch_related('images')
        [:6]
    )

    # Favori : est-ce que l'utilisateur a déjà sauvegardé cette annonce ?
    try:
        is_saved = (
            request.user.is_authenticated
            and BazarFavori.objects.filter(user=request.user, annonce=annonce).exists()
        )
        fav_count = annonce.favoris.count()
    except Exception:
        # Sécurité si la migration 0006 n'a pas encore été appliquée
        is_saved  = False
        fav_count = 0

    context = {
        'annonce':    annonce,
        'images':     annonce.images.all(),
        'similaires': similaires,
        'is_owner':   request.user.is_authenticated and request.user == annonce.seller,
        'is_saved':   is_saved,
        'fav_count':  fav_count,
    }
    return render(request, 'bazar/detail.html', context)


# ── Créer une annonce ───────────────────────────────────────────────────────────

@login_required
def annonce_create(request):
    """
    Formulaire de création d'une nouvelle annonce.
    URL: /bazar/vendre/
    """
    if request.method == 'POST':
        form = AnnonceForm(request.POST, request.FILES)
        if form.is_valid():
            annonce = form.save(commit=False)
            annonce.seller = request.user
            # Auto-remplir la région depuis le profil du vendeur
            if not annonce.region:
                annonce.region = getattr(request.user, 'region', '') or ''
            annonce.save()

            # Gérer les images uploadées (multiple files)
            images = request.FILES.getlist('images')
            limit  = _get_max_images(request.user)
            for i, img_file in enumerate(images[:limit]):
                AnnonceImage.objects.create(
                    annonce=annonce,
                    image=img_file,
                    is_primary=(i == 0),
                    order=i,
                )

            messages.success(request, 'Votre annonce a été publiée avec succès !')
            return redirect('bazar:detail', pk=annonce.pk)
        else:
            messages.error(request, 'Veuillez corriger les erreurs ci-dessous.')
    else:
        form = AnnonceForm()

    return render(request, 'bazar/create.html', {
        'form':       form,
        'max_images': _get_max_images(request.user),
    })


# ── Modifier une annonce ────────────────────────────────────────────────────────

@login_required
def annonce_edit(request, pk):
    """
    Modifier une annonce existante (vendeur uniquement).
    URL: /bazar/<pk>/modifier/
    """
    annonce = get_object_or_404(Annonce, pk=pk)

    if annonce.seller != request.user:
        messages.error(request, 'Vous n\'êtes pas autorisé à modifier cette annonce.')
        return redirect('bazar:detail', pk=annonce.pk)

    if request.method == 'POST':
        form = AnnonceForm(request.POST, request.FILES, instance=annonce)
        if form.is_valid():
            annonce = form.save()

            # Ajouter de nouvelles images
            new_images    = request.FILES.getlist('images')
            current_count = annonce.images.count()
            limit         = _get_max_images(request.user)
            for i, img_file in enumerate(new_images):
                if current_count + i >= limit:
                    break
                AnnonceImage.objects.create(
                    annonce=annonce,
                    image=img_file,
                    is_primary=False,
                    order=current_count + i,
                )

            messages.success(request, 'Annonce mise à jour.')
            return redirect('bazar:detail', pk=annonce.pk)
        else:
            messages.error(request, 'Veuillez corriger les erreurs.')
    else:
        form = AnnonceForm(instance=annonce)

    return render(request, 'bazar/edit.html', {
        'form':       form,
        'annonce':    annonce,
        'images':     annonce.images.all(),
        'max_images': _get_max_images(request.user),
    })


# ── Supprimer une image ─────────────────────────────────────────────────────────

@login_required
@require_POST
def delete_image(request, img_pk):
    """
    Supprimer une photo d'une annonce (AJAX POST).
    URL: /bazar/image/<img_pk>/supprimer/
    """
    img = get_object_or_404(AnnonceImage, pk=img_pk)
    if img.annonce.seller != request.user:
        return JsonResponse({'error': 'Non autorisé'}, status=403)

    annonce_pk = img.annonce.pk
    img.delete()

    # Ré-attribuer la photo principale si nécessaire
    if img.is_primary:
        first = AnnonceImage.objects.filter(annonce_id=annonce_pk).first()
        if first:
            first.is_primary = True
            first.save()

    return JsonResponse({'success': True})


# ── Marquer comme vendue ────────────────────────────────────────────────────────

@login_required
@require_POST
def mark_sold(request, pk):
    """
    Marquer une annonce comme vendue.
    URL: /bazar/<pk>/vendue/
    """
    annonce = get_object_or_404(Annonce, pk=pk)
    if annonce.seller != request.user:
        messages.error(request, 'Non autorisé.')
        return redirect('bazar:detail', pk=pk)

    annonce.status = 'vendue'
    annonce.save(update_fields=['status'])
    messages.success(request, 'Annonce marquée comme vendue.')
    return redirect('bazar:mes_annonces')


# ── Supprimer une annonce ───────────────────────────────────────────────────────

@login_required
@require_POST
def annonce_delete(request, pk):
    """
    Supprimer définitivement une annonce.
    URL: /bazar/<pk>/supprimer/
    """
    annonce = get_object_or_404(Annonce, pk=pk)
    if annonce.seller != request.user:
        messages.error(request, 'Non autorisé.')
        return redirect('bazar:index')

    annonce.delete()
    messages.success(request, 'Annonce supprimée.')
    return redirect('bazar:mes_annonces')


# ── Bump — remonter une annonce en tête ────────────────────────────────────────

@login_required
@require_POST
def bump_annonce(request, pk):
    """
    Rafraîchit une annonce (la fait remonter en tête des résultats).
    Cooldown : 1 bump toutes les 24 h.
    URL: /bazar/<pk>/bump/
    """
    annonce = get_object_or_404(Annonce, pk=pk)

    if annonce.seller != request.user:
        return JsonResponse({'error': 'Non autorisé'}, status=403)

    if annonce.status != 'active':
        return JsonResponse({'error': 'Seules les annonces actives peuvent être rafraîchies.'}, status=400)

    now = timezone.now()
    # Vérifier le cooldown
    if annonce.bumped_at:
        elapsed_h = (now - annonce.bumped_at).total_seconds() / 3600
        if elapsed_h < BUMP_COOLDOWN_H:
            remaining = int(BUMP_COOLDOWN_H - elapsed_h)
            return JsonResponse({
                'error': f'Vous pouvez rafraîchir à nouveau dans {remaining}h.',
                'cooldown': True,
                'remaining_h': remaining,
            }, status=429)

    Annonce.objects.filter(pk=pk).update(bumped_at=now)
    return JsonResponse({'success': True, 'bumped_at': now.isoformat()})


# ── Toggle statut — active ↔ pause ─────────────────────────────────────────────

@login_required
@require_POST
def toggle_status(request, pk):
    """
    Bascule le statut d'une annonce entre 'active' et 'pause'.
    AJAX POST. Répond JSON.
    URL: /bazar/<pk>/toggle-statut/
    """
    annonce = get_object_or_404(Annonce, pk=pk)

    if annonce.seller != request.user:
        return JsonResponse({'error': 'Non autorisé'}, status=403)

    if annonce.status == 'vendue':
        return JsonResponse({'error': 'Une annonce vendue ne peut pas être réactivée ici.'}, status=400)

    new_status = 'pause' if annonce.status == 'active' else 'active'
    Annonce.objects.filter(pk=pk).update(status=new_status)
    return JsonResponse({
        'success': True,
        'new_status': new_status,
        'label': 'Active' if new_status == 'active' else 'En pause',
    })


# ── Mes annonces ────────────────────────────────────────────────────────────────

# ── Helper vérification ────────────────────────────────────────────────────────

def _get_max_images(user):
    """Retourne le quota photos selon le statut de vérification du vendeur."""
    try:
        if user.seller_verification.is_approved:
            return MAX_IMAGES_VERIFIED
    except SellerVerification.DoesNotExist:
        pass
    return MAX_IMAGES


@login_required
def mes_annonces(request):
    """
    Liste des annonces du compte connecté.
    URL: /bazar/mes-annonces/
    """
    qs = (
        Annonce.objects
        .filter(seller=request.user)
        .prefetch_related('images')
        .order_by('-created_at')
    )
    # Récupérer le statut de vérification du compte
    try:
        verification = request.user.seller_verification
    except SellerVerification.DoesNotExist:
        verification = None

    context = {
        'annonces':     qs,
        'count_active': qs.filter(status='active').count(),
        'count_sold':   qs.filter(status='vendue').count(),
        'verification': verification,
    }
    return render(request, 'bazar/mes_annonces.html', context)


# ── Demande de vérification vendeur ────────────────────────────────────────────

@login_required
def request_verification(request):
    """
    Permet à un vendeur de soumettre une demande de vérification.
    Si une demande existe déjà, affiche son statut.
    URL: /bazar/verification/
    """
    try:
        verification = request.user.seller_verification
    except SellerVerification.DoesNotExist:
        verification = None

    if request.method == 'POST':
        # Empêcher une double soumission si déjà approuvé ou en attente
        if verification and verification.status in (
            SellerVerification.STATUS_PENDING,
            SellerVerification.STATUS_APPROVED,
        ):
            messages.info(request, 'Vous avez déjà une demande en cours ou votre compte est déjà vérifié.')
            return redirect('bazar:mes_annonces')

        message_text = request.POST.get('message', '').strip()[:2000]

        if verification:
            # Résoumission après refus
            verification.status      = SellerVerification.STATUS_PENDING
            verification.message     = message_text
            verification.admin_notes = ''
            verification.reviewed_at = None
            verification.reviewed_by = None
            verification.save()
            messages.success(request, 'Votre nouvelle demande a été envoyée. L\'admin l\'examinera prochainement.')
        else:
            SellerVerification.objects.create(
                seller=request.user,
                message=message_text,
            )
            messages.success(request, 'Demande de vérification envoyée ! L\'admin l\'examinera prochainement.')

        return redirect('bazar:mes_annonces')

    context = {
        'verification': verification,
    }
    return render(request, 'bazar/verification.html', context)


# ── Favoris ────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def toggle_favori(request, pk):
    """
    AJAX : ajoute ou retire une annonce des favoris de l'utilisateur connecté.
    Retourne JSON { saved: bool, count: int }
    """
    annonce = get_object_or_404(Annonce, pk=pk)
    fav, created = BazarFavori.objects.get_or_create(user=request.user, annonce=annonce)
    if not created:
        fav.delete()
        saved = False
    else:
        saved = True
    count = annonce.favoris.count()
    return JsonResponse({'saved': saved, 'count': count})


@login_required
def mes_favoris(request):
    """
    Page listant les annonces sauvegardées par l'utilisateur connecté.
    """
    favoris_qs = (
        BazarFavori.objects
        .filter(user=request.user)
        .select_related('annonce__seller')
        .prefetch_related('annonce__images')
    )
    # Exclure les annonces supprimées ou expirées
    favoris_qs = [f for f in favoris_qs if f.annonce.status != 'expiree']

    paginator = Paginator(favoris_qs, PAGE_SIZE)
    page      = paginator.get_page(request.GET.get('page'))

    return render(request, 'bazar/favoris.html', {
        'page_obj': page,
        'total':    paginator.count,
    })
