from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import BooleanField, Case, F, Q, When
from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Annonce, AnnonceImage, SellerVerification, BazarFavori
from .forms import AnnonceForm

# ── Constantes ─────────────────────────────────────────────────────────────────
PAGE_SIZE            = 12
MAX_IMAGES           = 8     # vendeur standard
MAX_IMAGES_VERIFIED  = 12    # vendeur vérifié (particulier)
MAX_IMAGES_PRO       = 20    # concessionnaire / boutique pro
BUMP_COOLDOWN_H      = 24    # heures entre deux bumps


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
        # Annotations : vendeur approuvé (any type) + vendeur pro (boutique)
        .annotate(
            seller_verified=Case(
                When(seller__seller_verification__status='approved', then=True),
                default=False,
                output_field=BooleanField(),
            ),
            seller_is_pro=Case(
                When(
                    seller__seller_verification__status='approved',
                    seller__seller_verification__seller_type='pro',
                    then=True,
                ),
                default=False,
                output_field=BooleanField(),
            ),
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
    try:
        annonce = Annonce.objects.get(pk=pk)
    except Annonce.DoesNotExist:
        messages.error(request, "Cette annonce n'existe pas ou a déjà été supprimée.")
        return redirect('bazar:mes_annonces')

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
        sv = user.seller_verification
        if sv.is_approved:
            if sv.seller_type == SellerVerification.SELLER_TYPE_PRO:
                return MAX_IMAGES_PRO
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
    Deux types : 'verified' (particulier) et 'pro' (concessionnaire/boutique).
    Si une demande existe déjà et est approuvée/en attente, affiche son statut.
    URL: /bazar/verification/
    """
    try:
        verification = request.user.seller_verification
    except SellerVerification.DoesNotExist:
        verification = None

    if request.method == 'POST':
        new_type = request.POST.get('seller_type', 'verified').strip()
        # Bloquer si en attente — pas de double soumission
        if verification and verification.status == SellerVerification.STATUS_PENDING:
            messages.info(request, 'Vous avez déjà une demande en cours.')
            return redirect('bazar:mes_annonces')
        # Bloquer si déjà approuvé au même niveau (ou déjà Pro)
        if verification and verification.status == SellerVerification.STATUS_APPROVED:
            if verification.seller_type == SellerVerification.SELLER_TYPE_PRO:
                messages.info(request, 'Votre boutique Pro est déjà active.')
                return redirect('bazar:mes_annonces')
            if new_type != SellerVerification.SELLER_TYPE_PRO:
                messages.info(request, 'Votre compte est déjà vérifié.')
                return redirect('bazar:mes_annonces')
            # Sinon : upgrade verified → pro — on continue

        # ── Données communes ──────────────────────────────────────────────────
        seller_type  = request.POST.get('seller_type', 'verified').strip()
        if seller_type not in (SellerVerification.SELLER_TYPE_VERIFIED, SellerVerification.SELLER_TYPE_PRO):
            seller_type = SellerVerification.SELLER_TYPE_VERIFIED
        message_text = request.POST.get('message', '').strip()[:2000]

        # ── Données boutique (uniquement pour type='pro') ─────────────────────
        boutique_name        = ''
        boutique_description = ''
        boutique_category    = ''
        boutique_phone       = ''
        boutique_address     = ''
        boutique_hours       = ''
        boutique_banner_file = None

        if seller_type == SellerVerification.SELLER_TYPE_PRO:
            boutique_name        = request.POST.get('boutique_name', '').strip()[:120]
            boutique_description = request.POST.get('boutique_description', '').strip()[:2000]
            boutique_category    = request.POST.get('boutique_category', '').strip()
            boutique_phone       = request.POST.get('boutique_phone', '').strip()[:30]
            boutique_address     = request.POST.get('boutique_address', '').strip()[:250]
            boutique_hours       = request.POST.get('boutique_hours', '').strip()[:250]
            boutique_banner_file = request.FILES.get('boutique_banner')

            if not boutique_name:
                messages.error(request, 'Le nom de la boutique est obligatoire pour une demande Pro.')
                context = {'verification': verification}
                return render(request, 'bazar/verification.html', context)

        if verification:
            # Résoumission après refus — mettre à jour les champs
            verification.seller_type        = seller_type
            verification.status             = SellerVerification.STATUS_PENDING
            verification.message            = message_text
            verification.admin_notes        = ''
            verification.reviewed_at        = None
            verification.reviewed_by        = None
            verification.boutique_name      = boutique_name
            verification.boutique_description = boutique_description
            verification.boutique_category  = boutique_category
            verification.boutique_phone     = boutique_phone
            verification.boutique_address   = boutique_address
            verification.boutique_hours     = boutique_hours
            if boutique_banner_file:
                verification.boutique_banner = boutique_banner_file
            verification.save()
            messages.success(request, 'Votre nouvelle demande a été envoyée. L\'admin l\'examinera prochainement.')
        else:
            kw = dict(
                seller=request.user,
                seller_type=seller_type,
                message=message_text,
                boutique_name=boutique_name,
                boutique_description=boutique_description,
                boutique_category=boutique_category,
                boutique_phone=boutique_phone,
                boutique_address=boutique_address,
                boutique_hours=boutique_hours,
            )
            sv = SellerVerification(**kw)
            if boutique_banner_file:
                sv.boutique_banner = boutique_banner_file
            sv.save()
            messages.success(request, 'Demande de vérification envoyée ! L\'admin l\'examinera prochainement.')

        return redirect('bazar:mes_annonces')

    context = {
        'verification': verification,
    }
    return render(request, 'bazar/verification.html', context)


# ── Page publique boutique concessionnaire ──────────────────────────────────────

def boutique_page(request, username):
    """
    Page publique d'un concessionnaire / vendeur pro.
    Affiche la bannière, les infos boutique et toutes ses annonces actives.
    URL: /bazar/boutique/<username>/
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    seller = get_object_or_404(User, username=username)

    try:
        verif = seller.seller_verification
    except SellerVerification.DoesNotExist:
        raise Http404

    if not verif.is_pro:
        raise Http404

    annonces_qs = (
        Annonce.objects
        .filter(seller=seller, status='active')
        .prefetch_related('images')
        .order_by(F('bumped_at').desc(nulls_last=True), '-created_at')
    )

    cat_filter = request.GET.get('cat', '').strip()
    if cat_filter:
        annonces_qs = annonces_qs.filter(category=cat_filter)

    paginator = Paginator(annonces_qs, PAGE_SIZE)
    page      = paginator.get_page(request.GET.get('page'))

    # Catégories disponibles dans cette boutique (pour le filtre)
    all_annonces = Annonce.objects.filter(seller=seller, status='active')
    categories_used = (
        all_annonces.values_list('category', flat=True)
        .distinct()
    )

    return render(request, 'bazar/boutique.html', {
        'boutique_seller': seller,
        'verif':           verif,
        'page_obj':        page,
        'total':           paginator.count,
        'cat_filter':      cat_filter,
        'categories_used': list(categories_used),
        'category_choices': dict(Annonce.CATEGORY_CHOICES),
    })


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
    try:
        favoris_qs = (
            BazarFavori.objects
            .filter(user=request.user)
            .select_related('annonce__seller')
            .prefetch_related('annonce__images')
        )
        # Exclure les annonces supprimées ou expirées
        favoris_qs = [f for f in favoris_qs if f.annonce.status != 'expiree']
    except Exception:
        favoris_qs = []

    paginator = Paginator(favoris_qs, PAGE_SIZE)
    page      = paginator.get_page(request.GET.get('page'))

    return render(request, 'bazar/favoris.html', {
        'page_obj': page,
        'total':    paginator.count,
    })
