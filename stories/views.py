import io
import logging

import requests as http_requests

from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from stories.models import Story, StoryView, StoryReaction, StoryReply

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
_AUDIO_MIME = {
    'audio/mpeg', 'audio/mp3', 'audio/ogg', 'audio/wav',
    'audio/webm', 'audio/aac', 'audio/x-m4a', 'audio/m4a',
    'audio/x-wav',
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


def _audio_url(story):
    """Retourne l'URL du fichier audio, ou None."""
    if not story.audio or not story.audio.name:
        return None
    try:
        return story.audio.url
    except Exception:
        return None


# ── Téléchargement audio depuis URL externe ───────────────────────────────────
_AUDIO_MAX_BYTES = 8 * 1024 * 1024  # 8 Mo

def _download_audio_from_url(url):
    """
    Télécharge un fichier audio depuis une URL externe.
    Retourne (InMemoryUploadedFile, mime_type) ou lève ValueError.
    """
    try:
        r = http_requests.get(url, timeout=15, stream=True,
                              headers={'User-Agent': 'Vazimba/1.0'})
        r.raise_for_status()
    except Exception as exc:
        raise ValueError(f"Impossible de télécharger l'audio : {exc}")

    content_type = r.headers.get('Content-Type', '').split(';')[0].strip().lower()
    # Certains serveurs renvoient application/octet-stream pour les MP3
    if content_type not in _AUDIO_MIME and not content_type.startswith('audio/'):
        raise ValueError(f"Type MIME non audio : {content_type}")

    data = b''
    for chunk in r.iter_content(chunk_size=32768):
        data += chunk
        if len(data) > _AUDIO_MAX_BYTES:
            raise ValueError("Fichier audio trop volumineux (max 8 Mo).")

    if not data:
        raise ValueError("Fichier audio vide.")

    # Deviner l'extension
    ext_map = {
        'audio/mpeg': 'mp3', 'audio/mp3': 'mp3',
        'audio/ogg': 'ogg', 'audio/wav': 'wav', 'audio/x-wav': 'wav',
        'audio/webm': 'webm', 'audio/aac': 'aac',
        'audio/x-m4a': 'm4a', 'audio/m4a': 'm4a',
    }
    ext = ext_map.get(content_type, 'mp3')
    filename = f'audio_from_url.{ext}'

    buf = io.BytesIO(data)
    file_obj = InMemoryUploadedFile(
        file=buf,
        field_name='audio',
        name=filename,
        content_type=content_type,
        size=len(data),
        charset=None,
    )
    return file_obj, content_type


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
        'audio_url':        _audio_url(story),
        'audio_type':       story.audio_type,
        'audio_trim_start': story.audio_trim_start,
        'caption':     story.caption,
        'bg_gradient': story.bg_gradient,
        'text_align':  story.text_align,
        'text_x':      story.text_x,
        'text_y':      story.text_y,
        'text_color':  story.text_color or '#ffffff',
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
        .order_by('user', 'created_at')   # chronologique : premier story = plus ancien
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

    all_groups = list(grouped.values())

    # Séparer le groupe de l'utilisateur courant des autres
    my_group    = None
    other_groups = []
    for g in all_groups:
        if request.user.is_authenticated and g['user'].id == request.user.id:
            my_group = g
        else:
            other_groups.append(g)

    ctx = {
        'seller_groups':  other_groups,   # autres utilisateurs
        'my_group':       my_group,        # groupe de l'utilisateur connecté
        'now':            now,
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
    text_color  = request.POST.get('text_color', '#ffffff').strip()[:20]
    link        = request.POST.get('link', '').strip()[:500]
    link_label  = request.POST.get('link_label', '').strip()[:60]
    media_file  = request.FILES.get('media')
    audio_file  = request.FILES.get('audio')
    audio_url_input = request.POST.get('audio_url', '').strip()  # URL externe
    try:
        audio_trim_start = max(0.0, float(request.POST.get('audio_trim_start', 0)))
    except (ValueError, TypeError):
        audio_trim_start = 0.0
    # Position du texte (0–100 %) — clampée côté serveur
    try:
        text_x = max(5.0, min(95.0, float(request.POST.get('text_x', 50))))
        text_y = max(5.0, min(95.0, float(request.POST.get('text_y', 50))))
    except (ValueError, TypeError):
        text_x, text_y = 50.0, 50.0

    # Validation
    if story_type in ('image', 'video', 'image_text') and not media_file:
        return JsonResponse({'error': 'Média requis pour ce type de story.'}, status=400)
    if story_type == 'text' and not caption:
        return JsonResponse({'error': 'Le texte ne peut pas être vide.'}, status=400)

    # Taille max : 50 Mo pour le média, 8 Mo pour l'audio
    if media_file and media_file.size > 50 * 1024 * 1024:
        return JsonResponse({'error': 'Fichier trop volumineux (max 50 Mo).'}, status=400)
    if audio_file and audio_file.size > _AUDIO_MAX_BYTES:
        return JsonResponse({'error': 'Fichier audio trop volumineux (max 8 Mo).'}, status=400)

    # Si l'utilisateur a fourni une URL externe, télécharger le fichier
    if audio_url_input and not audio_file:
        try:
            audio_file, _ = _download_audio_from_url(audio_url_input)
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)

    # Valider le MIME audio
    audio_type = ''
    if audio_file:
        audio_mime = (audio_file.content_type or '').split(';')[0].strip().lower()
        if audio_mime not in _AUDIO_MIME and not audio_mime.startswith('audio/'):
            return JsonResponse({'error': 'Format audio non supporté (MP3, OGG, WAV, AAC, M4A).'}, status=400)
        audio_type = audio_mime

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
            text_x      = text_x,
            text_y      = text_y,
            text_color  = text_color,
            audio            = audio_file,
            audio_type       = audio_type,
            audio_trim_start = audio_trim_start,
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
    ).select_related('user').order_by('user', 'created_at')   # chronologique

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


# ── RECHERCHE MUSIQUE (proxy Jamendo) ────────────────────────────────────────
@require_GET
def music_search(request):
    """
    Proxy vers l'API Jamendo pour rechercher de la musique libre de droits.
    Paramètres GET : q (recherche), limit (défaut 10)
    """
    query = request.GET.get('q', '').strip()
    limit = min(int(request.GET.get('limit', 10)), 20)
    client_id = getattr(settings, 'JAMENDO_CLIENT_ID', 'b6747d04')

    if not query:
        return JsonResponse({'tracks': []})

    try:
        resp = http_requests.get(
            'https://api.jamendo.com/v3.0/tracks/',
            params={
                'client_id':    client_id,
                'format':       'json',
                'limit':        limit,
                'search':       query,
                'audioformat':  'mp31',   # 128 kbps MP3 = léger
                'include':      'musicinfo',
                'groupby':      'artist_id',
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        tracks = []
        for t in data.get('results', []):
            tracks.append({
                'id':         t.get('id'),
                'name':       t.get('name', ''),
                'artist':     t.get('artist_name', ''),
                'duration':   t.get('duration', 0),
                'audio_url':  t.get('audio', ''),
                'image':      t.get('image', ''),
            })
        return JsonResponse({'tracks': tracks})
    except Exception as exc:
        _logger.warning('[music_search] Erreur Jamendo : %s', exc)
        return JsonResponse({'tracks': [], 'error': str(exc)}, status=200)


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


# ── VIEWERS LIST ──────────────────────────────────────────────────────────────
@login_required(login_url='login')
def get_story_viewers(request, story_id):
    """
    GET /stories/<id>/viewers/ — liste des viewers pour le créateur.
    Uniquement accessible par le propriétaire de la story.
    """
    try:
        story = Story.objects.get(pk=story_id)
    except Story.DoesNotExist:
        return JsonResponse({'error': 'Story introuvable.'}, status=404)

    if story.user != request.user:
        return JsonResponse({'error': 'Non autorisé.'}, status=403)

    viewers_qs = (
        StoryView.objects
        .filter(story=story)
        .select_related('viewer')
        .order_by('-viewed_at')
    )

    # Construire un dict par user_id pour fusionner vues + réactions
    rows = {}
    for sv in viewers_qs:
        uid = sv.viewer.id
        try:
            avatar = sv.viewer.profile_image.url
        except Exception:
            avatar = '/static/images/default_profile_image.png'
        rows[uid] = {
            'id':        uid,
            'username':  sv.viewer.username,
            'avatar':    avatar,
            'viewed_at': sv.viewed_at.strftime('%H:%M'),
            'emoji':     '',
        }

    # Ajouter les réactions au même dict (ou créer la ligne si pas encore vue)
    reactions_qs = (
        StoryReaction.objects
        .filter(story=story)
        .select_related('user')
        .order_by('-created_at')
    )
    for sr in reactions_qs:
        uid = sr.user.id
        if uid in rows:
            rows[uid]['emoji'] = sr.emoji
        else:
            try:
                avatar = sr.user.profile_image.url
            except Exception:
                avatar = '/static/images/default_profile_image.png'
            rows[uid] = {
                'id':        uid,
                'username':  sr.user.username,
                'avatar':    avatar,
                'viewed_at': '',
                'emoji':     sr.emoji,
            }

    # Réactions en premier, puis vues sans réaction (ordre d'insertion = -viewed_at)
    merged = (
        [r for r in rows.values() if r['emoji']] +
        [r for r in rows.values() if not r['emoji']]
    )

    # Réponses texte à cette story
    replies_qs = (
        StoryReply.objects
        .filter(story=story)
        .select_related('user')
        .order_by('-created_at')
    )
    replies = []
    for sr in replies_qs:
        try:
            avatar = sr.user.profile_image.url
        except Exception:
            avatar = '/static/images/default_profile_image.png'
        replies.append({
            'id':         sr.user.id,
            'username':   sr.user.username,
            'avatar':     avatar,
            'message':    sr.message,
            'created_at': sr.created_at.strftime('%H:%M'),
        })

    return JsonResponse({'viewers': merged, 'count': len(merged), 'replies': replies})


# ── Story Reply ───────────────────────────────────────────────────────────────
@login_required
@require_POST
def story_reply(request, story_id):
    """
    POST /stories/<id>/reply/
    Enregistre une réponse texte à une story + envoie une notification à l'auteur.
    """
    story = get_object_or_404(Story, pk=story_id)
    if story.user == request.user:
        return JsonResponse({'ok': False, 'error': 'Cannot reply to own story'}, status=400)

    import json as _json
    try:
        data    = _json.loads(request.body)
        message = data.get('message', '').strip()[:500]
    except Exception:
        message = request.POST.get('message', '').strip()[:500]

    if not message:
        return JsonResponse({'ok': False, 'error': 'Empty message'}, status=400)

    reply = StoryReply.objects.create(story=story, user=request.user, message=message)

    # Notification push + WebSocket à l'auteur
    try:
        from notification.models import PushSubscription, Notification
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        from django.contrib.humanize.templatetags.humanize import naturaltime
        from django.urls import reverse

        stories_url = request.build_absolute_uri(reverse('stories:list'))
        PushSubscription.send_notification(
            user=story.user,
            title='VAZIMBA — Story',
            body=f"{request.user.username} a répondu à votre story : {message[:60]}",
            url=stories_url,
        )
        notif = Notification.objects.create(
            target=story.user,
            from_user=request.user,
            redirect_url=stories_url,
            verb=f"{request.user.username} a répondu à votre story",
            read=False,
        )
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"user_{story.user.id}",
                {
                    "type": "post_action_notification",
                    "notification": {
                        "notification_type": "Post",
                        "notification_id": str(notif.pk),
                        "verb": notif.verb,
                        "natural_timestamp": str(naturaltime(notif.timestamp)),
                        "timestamp": str(notif.timestamp),
                        "is_read": "False",
                        "actions": {"redirect_url": stories_url},
                        "from": {"image_url": request.user.profile_image.url},
                    }
                }
            )
    except Exception:
        pass

    return JsonResponse({'ok': True, 'reply_id': reply.id})


# ── Story Reaction (toggle emoji) ─────────────────────────────────────────────
@login_required
def story_react(request, story_id):
    """
    POST /stories/<id>/react/
    {emoji: '❤️'} → toggle la réaction. Si l'emoji est différent du précédent,
    remplace. Retourne {ok, emoji|null, count}.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    import json as _json
    story = get_object_or_404(Story, id=story_id)
    try:
        data  = _json.loads(request.body)
        emoji = data.get('emoji', '').strip()
    except Exception:
        emoji = request.POST.get('emoji', '').strip()

    valid_emojis = {'❤️', '😂', '😮', '😢', '🔥'}
    if emoji not in valid_emojis:
        return JsonResponse({'ok': False, 'error': 'Invalid emoji'}, status=400)

    existing = StoryReaction.objects.filter(story=story, user=request.user).first()
    if existing:
        if existing.emoji == emoji:
            # Toggle off
            existing.delete()
            emoji = None
        else:
            existing.emoji = emoji
            existing.save(update_fields=['emoji'])
    else:
        StoryReaction.objects.create(story=story, user=request.user, emoji=emoji)

    count = StoryReaction.objects.filter(story=story).count()

    # Notifier l'auteur de la story (sauf si c'est lui qui réagit)
    if emoji and story.user != request.user:
        try:
            from notification.models import PushSubscription, Notification
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            from django.contrib.humanize.templatetags.humanize import naturaltime
            from django.urls import reverse

            stories_url = request.build_absolute_uri(reverse('stories:list'))
            PushSubscription.send_notification(
                user=story.user,
                title='VAZIMBA — Story',
                body=f"{request.user.username} a réagi {emoji} à votre story",
                url=stories_url,
            )
            notif = Notification.objects.create(
                target=story.user,
                from_user=request.user,
                redirect_url=stories_url,
                verb=f"{request.user.username} a réagi {emoji} à votre story",
                read=False,
            )
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f"user_{story.user.id}",
                    {
                        "type": "post_action_notification",
                        "notification": {
                            "notification_type": "Post",
                            "notification_id": str(notif.pk),
                            "verb": notif.verb,
                            "natural_timestamp": str(naturaltime(notif.timestamp)),
                            "timestamp": str(notif.timestamp),
                            "is_read": "False",
                            "actions": {"redirect_url": stories_url},
                            "from": {"image_url": request.user.profile_image.url},
                        }
                    }
                )
        except Exception:
            pass

    return JsonResponse({'ok': True, 'emoji': emoji, 'count': count})
