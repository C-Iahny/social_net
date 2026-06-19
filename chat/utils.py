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
    """
    hm = datetime.strftime(timestamp, "%H:%M")          # ex. "14:30"
    nd = naturalday(timestamp)                           # "today" / "yesterday" / date locale
    if nd == "today":
        return f"aujourd'hui at {hm}"
    elif nd == "yesterday":
        return f"hier at {hm}"
    else:
        # Format JJ/MM/AAAA lisible
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
        return dump_object

