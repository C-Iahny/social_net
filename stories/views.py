import logging

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from stories.models import Story, StoryView

_logger = logging.getLogger(__name__)


# ── MIME helpers ──────────────────────────────────────────────────────────────
_IMAGE_MIME = {
    'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
    'image/webp', 'image/bmp', 'image/heic', 'image/heif',
}
_VIDEO_MIME = {
    'video/mp4', 'video/webm', 'video/ogg', 'video/quicktime',
    'video/x-msvideo',
}


def _is_verified_seller(user):
    """Retourne True si l'utilisateur est un commerçant avec vérification approuvée."""
    try:
        return user.seller_verification.is_approved
    except Exception:
        return False


def _can_post_story(user):
    """Tous les utilisateurs connectés peuvent poster une story."""
    return user.is_authenticated


def _media_url(story):
    """Retourne l'URL du média."""
    if not story.media or not story.media.name:
        return None
    try:
        return story.media.url
    except Exception:
        return None


def _story_to_dict(story, viewer):
    """Sérialise une Story en dict JSON-compatible."""
    seen = False
    if viewer and viewer.is_authenticated:
        seen = StoryView.objects.filter(story=story, viewer=viewer).exists()

    try:
        avatar = story.user.profile_image.url
    except Exception:
        avatar = '/static/images/default_profile_image.png'

    return {
        'id':          story.id,
        'user_id':     story.user.id,
        'username':    story.user.username,
        'avatar':      avatar,
        'story_type':  story.story_type,
        'media_url':   _media_url(story),
        'media_type':  story.media_type,
        'caption':     story.caption,
        'bg_gradient': story.bg_gradient,
        'text_align':  story.text_align,
        'link':        story.link,
        'link_label':  story.link_label or 'Voir l\'offre',
        'created_at':  story.created_at.isoformat(),
        'expires_at':  story.expires_at.isoformat(),
        'time_left':   story.time_left_seconds,
        'view_count':  story.view_count,
        'seen':        seen,
        'is_mine':     (viewer and viewer.is_authenticated and story.user_id == viewer.id),
    }


# ── CONTEXT helper ────────────────────────────────────────────────────────────
def _seller_context(user):
    """Dict de contexte indiquant si l'utilisateur peut publier des stories."""
    return {'can_post_story': _can_post_story(user)}


# ── PAGE DÉDIÉE ───────────────────────────────────────────────────────────────
def stories_page(request):
    """
    Page /stories/ — toutes les stories actives de tous les utilisateurs.
    Accessible à tous (connectés ou non) en lecture.
    """
    now = timezone.now()

    # Stories actives de tous les utilisateurs, groupées par auteur
    stories_qs = (
        Story.objects
        .filter(expires_at__gt=now)
        .select_related('user')
        .order_by('user', '-created_at')
    )

    # Grouper par utilisateur
    grouped = {}
    for story in stories_qs:
        uid = story.user_id
        if uid not in grouped:
            try:
                avatar = story.user.profile_image.url
            except Exception:
                avatar = '/static/images/default_profile_image.png'
            grouped[uid] = {
                'user':    story.user,
                'avatar':  avatar,
                'stories': [],
            }
        grouped[uid]['stories'].append(story)

    seller_groups = list(grouped.values())

    ctx = {
        'seller_groups':   seller_groups,
        'now':             now,
    }
    ctx.update(_seller_context(request.user))
    return render(request, 'stories/story_list.html', ctx)


# ── CREATE ────────────────────────────────────────────────────────────────────
@login_required(login_url='login')
@require_POST
def create_story(request):
    story_type  = request.POST.get('story_type', 'image')
    caption     = request.POST.get('caption', '').strip()[:200]
    bg_gradient = request.POST.get('bg_gradient', 'grad_cyan')
    text_align  = request.POST.get('text_align', 'center')
    link        = request.POST.get('link', '').strip()[:500]
    link_label  = request.POST.get('link_label', '').strip()[:60]
    media_file  = request.FILES.get('media')

    # Validation
    if story_type in ('image', 'video', 'image_text') and not media_file:
        return JsonResponse({'error': 'Média requis pour ce type de story.'}, status=400)
    if story_type == 'text' and not caption:
        return JsonResponse({'error': 'Le texte ne peut pas être vide.'}, status=400)

    # Taille max : 50 Mo
    if media_file and media_file.size > 50 * 1024 * 1024:
        return JsonResponse({'error': 'Fichier trop volumineux (max 50 Mo).'}, status=400)

    # Détecter le type média
    media_type = ''
    if media_file:
        mime = (media_file.content_type or '').split(';')[0].strip().lower()
        if mime in _IMAGE_MIME:
            media_type = 'image'
        elif mime in _VIDEO_MIME:
            media_type = 'video'
        else:
            return JsonResponse({'error': 'Format de fichier non supporté.'}, status=400)

    try:
        story = Story.objects.create(
            user        = request.user,
            story_type  = story_type,
            media       = media_file,
            media_type  = media_type,
            caption     = caption,
            bg_gradient = bg_gradient,
            text_align  = text_align,
            link        = link,
            link_label  = link_label,
        )
    except Exception as e:
        _logger.exception("create_story FAILED: %s", e)
        return JsonResponse({'error': f'Erreur lors de la publication : {e}'}, status=500)

    return JsonResponse({'ok': True, 'story': _story_to_dict(story, request.user)})


# ── DELETE ────────────────────────────────────────────────────────────────────
@login_required(login_url='login')
@require_POST
def delete_story(request, story_id):
    try:
        story = Story.objects.get(pk=story_id, user=request.user)
    except Story.DoesNotExist:
        return JsonResponse({'error': 'Story introuvable.'}, status=404)
    story.delete()
    return JsonResponse({'ok': True})


# ── MARK VIEWED ───────────────────────────────────────────────────────────────
@login_required(login_url='login')
@require_POST
def mark_viewed(request, story_id):
    try:
        story = Story.objects.get(pk=story_id)
    except Story.DoesNotExist:
        return JsonResponse({'error': 'Story introuvable.'}, status=404)
    if story.is_active:
        StoryView.objects.get_or_create(story=story, viewer=request.user)
    return JsonResponse({'ok': True})


# ── FEED : stories de tous les commerçants vérifiés ──────────────────────────
@require_GET
def get_feed_stories(request):
    """
    Retourne les stories actives de TOUS les commerçants vérifiés approuvés.
    Si l'utilisateur est connecté, on indique également ses propres stories
    et les stories déjà vues.
    Accessible aux non-connectés (mode lecture seule, seen=False).
    """
    now = timezone.now()
    viewer = request.user if request.user.is_authenticated else None

    # Stories actives de tous les utilisateurs
    stories_qs = Story.objects.filter(
        expires_at__gt=now,
    ).select_related('user').order_by('user', '-created_at')

    # Grouper par utilisateur
    grouped = {}
    for story in stories_qs:
        try:
            uid = story.user_id
            if uid not in grouped:
                try:
                    avatar = story.user.profile_image.url
                except Exception:
                    avatar = '/static/images/default_profile_image.png'
                grouped[uid] = {
                    'user_id':    uid,
                    'username':   story.user.username,
                    'avatar':     avatar,
                    'stories':    [],
                    'has_unseen': False,
                    'is_mine':    (viewer and uid == viewer.id),
                }
            s = _story_to_dict(story, viewer)
            grouped[uid]['stories'].append(s)
            if not s['seen']:
                grouped[uid]['has_unseen'] = True
        except Exception as exc:
            _logger.exception('[Stories] Erreur story %s : %s', story.id, exc)
            continue

    # Trier : soi-même en premier, puis non vus d'abord
    result = sorted(
        grouped.values(),
        key=lambda g: (
            0 if (viewer and g['user_id'] == viewer.id) else 1,
            0 if g['has_unseen'] else 1,
        )
    )
    return JsonResponse({'groups': result})


# ── MES STORIES ───────────────────────────────────────────────────────────────
@login_required(login_url='login')
@require_GET
def get_my_stories(request):
    now = timezone.now()
    stories_qs = Story.objects.filter(
        user=request.user, expires_at__gt=now
    ).select_related('user').order_by('-created_at')
    return JsonResponse({
        'stories': [_story_to_dict(s, request.user) for s in stories_qs]
    })


# ── STORIES D'UN PROFIL ───────────────────────────────────────────────────────
@require_GET
def get_profile_stories(request, user_id):
    from account.models import Account
    try:
        profile_user = Account.objects.get(pk=user_id)
    except Account.DoesNotExist:
        return JsonResponse({'stories': []})
    now = timezone.now()
    stories_qs = Story.objects.filter(
        user=profile_user, expires_at__gt=now
    ).select_related('user').order_by('-created_at')
    viewer = request.user if request.user.is_authenticated else None
    return JsonResponse({
        'stories': [_story_to_dict(s, viewer) for s in stories_qs]
    })
