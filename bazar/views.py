from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import Annonce, AnnonceImage
from .forms import AnnonceForm

# ── Constantes ─────────────────────────────────────────────────────────────────
PAGE_SIZE = 12
MAX_IMAGES = 8


# ── Liste / Explore ─────────────────────────────────────────────────────────────

def bazar_index(request):
    """
    Page principale du Bazar : liste des annonces actives avec filtres.
    URL: /bazar/
    """
    qs = Annonce.objects.filter(status='active').select_related('seller').prefetch_related('images')

    # ── Filtres URL ──────────────────────────────────────────────────────────
    q         = request.GET.get('q', '').strip()
    category  = request.GET.get('cat', '').strip()
    condition = request.GET.get('cond', '').strip()
    location  = request.GET.get('loc', '').strip()
    price_min = request.GET.get('pmin', '').strip()
    price_max = request.GET.get('pmax', '').strip()
    sort      = request.GET.get('sort', 'recent')

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

    if sort == 'price_asc':
        qs = qs.order_by('price', '-created_at')
    elif sort == 'price_desc':
        qs = qs.order_by('-price', '-created_at')
    elif sort == 'popular':
        qs = qs.order_by('-views_count', '-created_at')
    else:
        qs = qs.order_by('-created_at')

    # ── Pagination ────────────────────────────────────────────────────────────
    paginator = Paginator(qs, PAGE_SIZE)
    page_obj  = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj':   page_obj,
        'categories': Annonce.CATEGORY_CHOICES,
        'conditions': Annonce.CONDITION_CHOICES,
        'q':          q,
        'sel_cat':    category,
        'sel_cond':   condition,
        'sel_loc':    location,
        'sel_pmin':   price_min,
        'sel_pmax':   price_max,
        'sort':       sort,
        'total':      paginator.count,
    }
    return render(request, 'bazar/index.html', context)


# ── Détail d'une annonce ────────────────────────────────────────────────────────

def annonce_detail(request, pk):
    """
    Page de détail d'une annonce.
    URL: /bazar/<pk>/
    """
    annonce = get_object_or_404(Annonce, pk=pk)

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

    context = {
        'annonce':    annonce,
        'images':     annonce.images.all(),
        'similaires': similaires,
        'is_owner':   request.user.is_authenticated and request.user == annonce.seller,
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
            annonce.save()

            # Gérer les images uploadées (multiple files)
            images = request.FILES.getlist('images')
            for i, img_file in enumerate(images[:MAX_IMAGES]):
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

    return render(request, 'bazar/create.html', {'form': form})


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
            new_images = request.FILES.getlist('images')
            current_count = annonce.images.count()
            for i, img_file in enumerate(new_images):
                if current_count + i >= MAX_IMAGES:
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
        'form':    form,
        'annonce': annonce,
        'images':  annonce.images.all(),
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


# ── Mes annonces ────────────────────────────────────────────────────────────────

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
    context = {
        'annonces': qs,
        'count_active': qs.filter(status='active').count(),
        'count_sold':   qs.filter(status='vendue').count(),
    }
    return render(request, 'bazar/mes_annonces.html', context)
