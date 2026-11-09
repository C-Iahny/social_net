import json
from django.conf import settings
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.shortcuts import render
from .models import PushSubscription
from django.contrib.contenttypes.models import ContentType


@login_required(login_url='login')
@require_GET
def vapid_public_key(request):
    """Retourne la clé publique VAPID au client."""
    return JsonResponse({'publicKey': settings.VAPID_PUBLIC_KEY})


@login_required(login_url='login')
@require_POST
def push_subscribe(request):
    """Enregistre ou met à jour une subscription push."""
    try:
        data     = json.loads(request.body)
        endpoint = data.get('endpoint', '')
        p256dh   = data.get('keys', {}).get('p256dh', '')
        auth     = data.get('keys', {}).get('auth', '')

        if not endpoint or not p256dh or not auth:
            return JsonResponse({'error': 'Données incomplètes'}, status=400)

        sub, created = PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                'user':   request.user,
                'p256dh': p256dh,
                'auth':   auth,
            }
        )
        return JsonResponse({'ok': True, 'created': created})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required(login_url='login')
@require_POST
def push_unsubscribe(request):
    """Supprime une subscription push."""
    try:
        data     = json.loads(request.body)
        endpoint = data.get('endpoint', '')
        PushSubscription.objects.filter(endpoint=endpoint, user=request.user).delete()
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def _badge_counts(user):
    """Compteurs des badges cloche / messages pour `user`."""
    from notification.models import Notification
    from friend.models import FriendRequest, FriendList
    from chat.models import UnreadChatRoomMessages
    from post.models import Post as PostModel
    fr_ct   = ContentType.objects.get_for_model(FriendRequest)
    fl_ct   = ContentType.objects.get_for_model(FriendList)
    chat_ct = ContentType.objects.get_for_model(UnreadChatRoomMessages)
    post_ct = ContentType.objects.get_for_model(PostModel)

    from video.models import LiveRoom
    live_ct = ContentType.objects.get_for_model(LiveRoom)
    # FIX: inclure post_ct (likes + commentaires + reposts) et live_ct dans le compteur badge
    general_count = Notification.objects.filter(
        target=user, content_type__in=[fr_ct, fl_ct, post_ct, live_ct], read=False,
    ).count()

    chat_count = Notification.objects.filter(
        target=user, content_type=chat_ct,
    ).count()

    return {'general': general_count, 'chat': chat_count}


@login_required(login_url='login')
@require_GET
def unread_counts(request):
    """
    HTTP fallback for notification badge counts.
    Returns {"general": N, "chat": N} — used when WebSocket is unavailable.
    """
    return JsonResponse(_badge_counts(request.user))


@login_required(login_url='login')
def notification_journal(request):
    """Page journal de toutes les notifications de l'utilisateur."""
    from notification.models import Notification
    from friend.models import FriendRequest, FriendList
    from chat.models import UnreadChatRoomMessages
    from post.models import Post as PostModel

    from video.models import LiveRoom
    fr_ct   = ContentType.objects.get_for_model(FriendRequest)
    fl_ct   = ContentType.objects.get_for_model(FriendList)
    chat_ct = ContentType.objects.get_for_model(UnreadChatRoomMessages)
    post_ct = ContentType.objects.get_for_model(PostModel)
    live_ct = ContentType.objects.get_for_model(LiveRoom)

    notifications = (
        Notification.objects
        .filter(target=request.user, content_type__in=[fr_ct, fl_ct, post_ct, live_ct])
        .select_related('from_user', 'content_type')
        .order_by('-timestamp')
    )

    # On fige la liste AVANT de marquer lu : la page affiche ainsi une
    # dernière fois les non-lues en surbrillance (.vz-card--unread).
    items = list(notifications[:100])
    notifications.filter(read=False).update(read=True)

    return render(request, 'notification/journal.html', {
        'notifications': items,
    })


@login_required(login_url='login')
@require_POST
def mark_read(request, pk):
    """Marque UNE notification comme lue (clic sur une carte, repli HTTP du WebSocket)."""
    from notification.models import Notification
    Notification.objects.filter(pk=pk, target=request.user, read=False).update(read=True)
    return JsonResponse(_badge_counts(request.user))
