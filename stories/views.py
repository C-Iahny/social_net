import os
import json
import logging
<<<<<<< Updated upstream
import cloudinary.uploader
=======
>>>>>>> Stashed changes
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q

from friend.models import FriendList
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


def _media_url(story):
<<<<<<< Updated upstream
    """Génère l'URL Cloudinary correcte selon media_type (image ou video)."""
    if not story.media or not story.media.name:
        return None
    try:
        import cloudinary
        rt = 'video' if story.media_type == 'video' else 'image'
        resource = cloudinary.CloudinaryResource(story.media.name, default_resource_type=rt)
        return resource.url
    except Exception:
        try:
            return story.media.url
        except Exception:
            return None
=======
    """Retourne l'URL du média (servi par R2)."""
    if not story.media or not story.media.name:
        return None
    try:
        return story.media.url
    except Exception:
        return None
>>>>>>> Stashed changes


def _story_to_dict(story, viewer):
    """Sérialise une Story en dict JSON-compatible."""
    seen = StoryView.objects.filter(story=story, viewer=viewer).exists()
    data = {
        'id':          story.id,
        'user_id':     story.user.id,
        'username':    story.user.username,
        'avatar':      story.user.profile_image.url,
        'story_type':  story.story_type,
        'media_url':   _media_url(story),
        'media_type':  story.media_type,
        'caption':     story.caption,
        'bg_gradient': story.bg_gradient,
        'text_align':  story.text_align,
        'created_at':  story.created_at.isoformat(),
        'expires_at':  story.expires_at.isoformat(),
        'time_left':   story.time_left_seconds,
        'view_count':  story.view_count,
        'seen':        seen,
    }
    return data


# ── CREATE ────────────────────────────────────────────────────────────────────
@login_required(login_url='login')
@require_POST
def create_story(request):
    story_type  = request.POST.get('story_type', 'image')
    caption     = request.POST.get('caption', '').strip()[:200]
    bg_gradient = request.POST.get('bg_gradient', 'grad_cyan')
    text_align  = request.POST.get('text_align', 'center')
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
<<<<<<< Updated upstream
        if media_file and media_type == 'video':
            # Upload direct Cloudinary avec resource_type='video'
            # (MediaCloudinaryStorage n'accepte que les images)
            media_file.seek(0)
            resp = cloudinary.uploader.upload(
                media_file,
                resource_type='video',
                folder='stories',
                use_filename=True,
                unique_filename=True,
            )
            public_id = resp['public_id']
            _logger.info("Story vidéo uploadée : public_id=%s", public_id)

            story = Story(
                user        = request.user,
                story_type  = story_type,
                media_type  = media_type,
                caption     = caption,
                bg_gradient = bg_gradient,
                text_align  = text_align,
            )
            story.media.name = public_id
            story.save()

        else:
            # Image ou texte — stockage via le backend Django normal
            story = Story.objects.create(
                user        = request.user,
                story_type  = story_type,
                media       = media_file,
                media_type  = media_type,
                caption     = caption,
                bg_gradient = bg_gradient,
                text_align  = text_align,
            )

=======
        # R2 gère images ET vidéos via le même backend Django standard
        story = Story.objects.create(
            user        = request.user,
            story_type  = story_type,
            media       = media_file,
            media_type  = media_type,
            caption     = caption,
            bg_gradient = bg_gradient,
            text_align  = text_align,
        )
>>>>>>> Stashed changes
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


# ── FEED : stories des amis ───────────────────────────────────────────────────
@login_required(login_url='login')
@require_GET
def get_feed_stories(request):
    """
    Retourne les stories actives de l'utilisateur connecté + ses amis.
    Regroupées par utilisateur, triées : non-vues d'abord.
    """
    now = timezone.now()

    # Récupérer la liste d'amis
    try:
        friend_list = FriendList.objects.get(user=request.user)
        friends = list(friend_list.friends.all())
    except FriendList.DoesNotExist:
        friends = []

    # Inclure soi-même
    users_to_show = [request.user] + friends

    # Récupérer toutes les stories actives
    stories_qs = Story.objects.filter(
        user__in=users_to_show,
        expires_at__gt=now,
    ).select_related('user').order_by('user', '-created_at')

    # Grouper par utilisateur
    grouped = {}
    for story in stories_qs:
        uid = story.user.id
        if uid not in grouped:
            grouped[uid] = {
                'user_id':   story.user.id,
                'username':  story.user.username,
                'avatar':    story.user.profile_image.url,
                'is_me':     story.user.id == request.user.id,
                'stories':   [],
                'all_seen':  True,
            }
        s = _story_to_dict(story, request.user)
        grouped[uid]['stories'].append(s)
        if not s['seen']:
            grouped[uid]['all_seen'] = False

    # Trier : soi-même en premier, puis non-vus, puis vus
    result = sorted(
        grouped.values(),
        key=lambda g: (
            0 if g['is_me'] else 1,
            1 if g['all_seen'] else 0,
        )
    )

    return JsonResponse({'groups': result})


# ── MES STORIES (pour la page profil) ────────────────────────────────────────
@login_required(login_url='login')
@require_GET
def get_my_stories(request):
    now = timezone.now()
    stories = Story.objects.filter(
        user=request.user,
        expires_at__gt=now,
    ).order_by('-created_at')
    data = [_story_to_dict(s, request.user) for s in stories]
    return JsonResponse({'stories': data, 'count': len(data)})


# ── STORIES D'UN PROFIL PUBLIQUE (pour la page profil d'un ami) ──────────────
@login_required(login_url='login')
@require_GET
def get_profile_stories(request, user_id):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    try:
        profile_user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Utilisateur introuvable.'}, status=404)

    # Vérifier que l'on est ami (sauf si c'est soi-même)
    if profile_user != request.user:
        try:
            fl = FriendList.objects.get(user=request.user)
            if profile_user not in fl.friends.all():
                return JsonResponse({'stories': [], 'count': 0})
        except FriendList.DoesNotExist:
            return JsonResponse({'stories': [], 'count': 0})

    now = timezone.now()
    stories = Story.objects.filter(
        user=profile_user,
        expires_at__gt=now,
    ).order_by('-created_at')
    data = [_story_to_dict(s, request.user) for s in stories]
    return JsonResponse({'stories': data, 'count': len(data)})
