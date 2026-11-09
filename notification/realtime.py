"""
Diffusion temps réel des notifications.

Une seule porte de sortie vers le channel layer, branchée sur les signaux du
modèle Notification (notification/signals.py) : toute notification créée ou
modifiée, où que ce soit dans le code (amis, posts, stories, groupes, resto,
chat), est poussée au groupe personnel `user_<id>` de son destinataire sans
que chaque vue ait à le faire elle-même.
"""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)

CHAT_CNAME = 'UnreadChatRoomMessages'


def _send(group, event):
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(group, event)
    except Exception as e:  # loop déjà actif dans ce thread, Redis absent…
        logger.debug('realtime: group_send %s ignoré : %s', event.get('type'), e)


def push_notification(notif):
    """Pousse une notification fraîchement enregistrée à son destinataire."""
    from .utils import LazyNotificationEncoder
    try:
        cname = notif.get_content_object_type()
    except Exception:
        cname = None
    if cname == CHAT_CNAME:
        obj = notif.content_object
        _send(f'user_{notif.target_id}', {
            'type':         'chat.unread_notif',
            'msg_type':     10,
            'from_user_id': notif.from_user_id,
            'count':        getattr(obj, 'count', 0) or 0,
        })
        return
    try:
        # Serializer « python » : renvoie déjà une liste de dicts JSON-compatibles
        data = LazyNotificationEncoder().serialize([notif])[0]
    except Exception as e:
        logger.debug('realtime: sérialisation impossible : %s', e)
        return
    if not data:
        return
    _send(f'user_{notif.target_id}', {'type': 'post_action_notification', 'notification': data})


def push_counts(user_id):
    """Demande au client de rafraîchir ses badges (après suppression / lecture)."""
    _send(f'user_{user_id}', {'type': 'notif.counts'})
