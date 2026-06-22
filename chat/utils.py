from datetime import datetime
from django.contrib.humanize.templatetags.humanize import naturalday
from django.core.serializers.python import Serializer

from chat.models import PrivateChatRoom
from chat.constants import *


def find_or_create_private_chat(user1, user2):
    try:
        chat = PrivateChatRoom.objects.get(user1=user1, user2=user2)
    except PrivateChatRoom.DoesNotExist:
        try:
            chat = PrivateChatRoom.objects.get(user1=user2, user2=user1)
        except PrivateChatRoom.DoesNotExist:
            chat = PrivateChatRoom(user1=user1, user2=user2)
            chat.save()
    return chat


def calculate_timestamp(timestamp):
    """
    Retourne TOUJOURS "date at HH:MM" pour que le JS puisse séparer date et heure.
    - aujourd'hui at 14:30
    - hier at 09:05
    - 15/06/2026 at 14:30

    Note: naturalday() retourne "today"/"yesterday" en anglais ou
    "aujourd'hui"/"hier" en français selon LANGUAGE_CODE.
    On gère les deux pour être robuste.
    """
    hm = datetime.strftime(timestamp, "%H:%M")
    nd = naturalday(timestamp).lower()          # normalise la casse
    if nd in ("today", "aujourd'hui"):
        return f"aujourd'hui at {hm}"
    elif nd in ("yesterday", "hier"):
        return f"hier at {hm}"
    else:
        date_str = datetime.strftime(timestamp, "%d/%m/%Y")
        return f"{date_str} at {hm}"



class LazyRoomChatMessageEncoder(Serializer):
    def get_dump_object(self, obj):
        dump_object = {}
        # Determine message type
        if obj.file:
            dump_object['msg_type']  = MSG_TYPE_FILE
            dump_object['file_url']  = str(obj.file.url)
            dump_object['file_name'] = obj.file.name.split('/')[-1]
            dump_object['file_type'] = obj.file_type or 'document'
        else:
            dump_object['msg_type'] = MSG_TYPE_MESSAGE
        dump_object['msg_id']            = str(obj.id)
        dump_object['user_id']           = str(obj.user.id)
        dump_object['username']          = str(obj.user.username)
        dump_object['message']           = str(obj.content)
        dump_object['profile_image']     = str(obj.user.profile_image.url)
        dump_object['natural_timestamp'] = calculate_timestamp(obj.timestamp)
        # ── Citation (reply) ────────────────────────────────────────────────
        if obj.reply_to_id:
            try:
                rt = obj.reply_to
                body = rt.content[:100] if rt.content else f'[{rt.file_type or "fichier"}]'
                dump_object['reply_to_id']       = str(rt.id)
                dump_object['reply_to_username'] = str(rt.user.username)
                dump_object['reply_to_content']  = body
            except Exception:
                pass
        # ── Réactions emoji ──────────────────────────────────────────────────
        try:
            from collections import defaultdict
            grouped = defaultdict(list)
            for r in obj.reactions.select_related('user').all():
                grouped[r.emoji].append(r.user.username)
            if grouped:
                dump_object['reactions'] = [
                    {'emoji': k, 'count': len(v), 'users': v}
                    for k, v in grouped.items()
                ]
        except Exception:
            pass
        return dump_object

