from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q

from .models import LieuTouristique, GuideTouristique, LieuImage, LIEU_CATEGORY_CHOICES, REGION_CHOICES


def tourisme_home(request):
    """Page d'accueil tourisme: lieux en vedette + guides vérifiés"""
    lieux_vedette = (
        LieuTouristique.objects.filter(is_approved=True)
        .prefetch_related('images')
        .order_by('-views_count')[:8]
    )
    guides = (
        GuideTouristique.objects.filter(is_verified=True, is_active=True)
        .select_related('user')
        [:6]
    )
    categories = LIEU_CATEGORY_CHOICES
    return render(request, 'tourisme/home.html', {
        'lieux_vedette': lieux_vedette,
        'guides':        guides,
        'categories':    categories,
    })


def lieux_list(request):
    """Liste de tous les lieux touristiques approuvés"""
    qs = LieuTouristique.objects.filter(is_approved=True).prefetch_related('images')

    q        = request.GET.get('q', '').strip()
    category = request.GET.get('cat', '').strip()
    region   = request.GET.get('region', '').strip()

    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
    if category:
        qs = qs.filter(category=category)
    if region:
        qs = qs.filter(region=region)

    qs = qs.order_by('-views_count', '-created_at')
    paginator = Paginator(qs, 12)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'tourisme/lieux_list.html', {
        'page_obj':   page_obj,
        'categories': LIEU_CATEGORY_CHOICES,
        'regions':    REGION_CHOICES,
        'q':          q,
        'sel_cat':    category,
        'sel_region': region,
        'total':      paginator.count,
    })


def lieu_detail(request, slug):
    """Page de détail d'un lieu touristique"""
    lieu = get_object_or_404(LieuTouristique, slug=slug, is_approved=True)
    LieuTouristique.objects.filter(pk=lieu.pk).update(views_count=lieu.views_count + 1)

    # Guides qui couvrent ce lieu
    guides = lieu.guides.filter(is_verified=True, is_active=True).select_related('user')[:4]

    # Lieux similaires
    similaires = (
        LieuTouristique.objects.filter(is_approved=True, category=lieu.category)
        .exclude(pk=lieu.pk)
        .prefetch_related('images')[:4]
    )

    return render(request, 'tourisme/lieu_detail.html', {
        'lieu':       lieu,
        'images':     lieu.images.all(),
        'guides':     guides,
        'similaires': similaires,
    })


def guides_list(request):
    """Liste des guides touristiques vérifiés"""
    qs = GuideTouristique.objects.filter(is_active=True).select_related('user')

    verified_only = request.GET.get('verified', '')
    region        = request.GET.get('region', '').strip()
    q             = request.GET.get('q', '').strip()

    if verified_only:
        qs = qs.filter(is_verified=True)
    if q:
        qs = qs.filter(
            Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q) |
            Q(bio__icontains=q) | Q(specialities__icontains=q) |
            Q(languages__icontains=q)
        )
    if region:
        qs = qs.filter(regions_covered__icontains=region)

    qs = qs.order_by('-is_verified', '-created_at')
    paginator = Paginator(qs, 12)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'tourisme/guides_list.html', {
        'page_obj':      page_obj,
        'regions':       REGION_CHOICES,
        'verified_only': verified_only,
        'sel_region':    region,
        'q':             q,
        'total':         paginator.count,
    })


def guide_profile(request, pk):
    """Page profil d'un guide touristique"""
    guide = get_object_or_404(
        GuideTouristique.objects.select_related('user').prefetch_related('lieux_favoris__images'),
        pk=pk
    )
    is_owner = request.user.is_authenticated and request.user == guide.user
    return render(request, 'tourisme/guide_profile.html', {
        'guide':    guide,
        'is_owner': is_owner,
    })


@login_required
def guide_register(request):
    """Devenir guide touristique (créer ou modifier son profil)"""
    guide = None
    try:
        guide = request.user.guide_profile
    except GuideTouristique.DoesNotExist:
        pass

    if request.method == 'POST':
        data = request.POST
        if guide is None:
            guide = GuideTouristique(user=request.user)

        guide.bio              = data.get('bio', '').strip()
        guide.languages        = data.get('languages', '').strip()
        guide.regions_covered  = data.get('regions_covered', '').strip()
        guide.transport_modes  = data.get('transport_modes', '').strip()
        guide.specialities     = data.get('specialities', '').strip()
        guide.conditions       = data.get('conditions', '').strip()
        guide.phone            = data.get('phone', '').strip()
        try:
            guide.prix_jour = int(data.get('prix_jour', '') or 0) or None
        except ValueError:
            guide.prix_jour = None
        try:
            guide.years_experience = int(data.get('years_experience', '') or 0)
        except ValueError:
            guide.years_experience = 0
        try:
            guide.max_group_size = int(data.get('max_group_size', '') or 10)
        except ValueError:
            guide.max_group_size = 10

        if request.FILES.get('photo'):
            guide.photo = request.FILES['photo']

        guide.save()
        messages.success(request, 'Votre profil de guide a été enregistré. Un administrateur le vérifiera bientôt.')
        return redirect('tourisme:guide_profile', pk=guide.pk)

    return render(request, 'tourisme/guide_register.html', {
        'guide':   guide,
        'regions': REGION_CHOICES,
    })
