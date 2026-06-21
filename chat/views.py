from django.shortcuts import render, redirect
from django.urls import reverse
from urllib.parse import urlencode
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from itertools import chain

import json
import os

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from account.models import Account
from chat.models import PrivateChatRoom, RoomChatMessage, UnreadChatRoomMessages
from chat.utils import find_or_create_private_chat
from chat.constants import MSG_TYPE_CALL_REJECT

DEBUG = False

# ── MIME → file_type mapping ──────────────────────────────────────────────────
_IMAGE_TYPES = {'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
                'image/webp', 'image/bmp', 'image/tiff', 'image/heic', 'image/heif'}
_VIDEO_TYPES = {'video/mp4', 'video/webm', 'video/ogg', 'video/quicktime',
                'video/x-msvideo', 'video/x-matroska'}

def private_chat_room_view(request, *args, **kwargs):
	user = request.user

	# Redirect them if not authenticated
	if not user.is_authenticated:
		next_url = request.get_full_path()
		return redirect(f"/login/?next={next_url}")

	room_id    = request.GET.get("room_id")
	user_id    = request.GET.get("user_id")     # ouvrir directement avec cet utilisateur
	annonce_pk = request.GET.get("annonce")     # référence annonce bazar (optionnel)

	context = {}

	if room_id:
		try:
			room = PrivateChatRoom.objects.get(pk=room_id)
			context["room"] = room
		except PrivateChatRoom.DoesNotExist:
			pass
	elif user_id:
		# Ouvrir (ou créer) la conversation avec l'utilisateur demandé
		try:
			other_user = Account.objects.get(pk=user_id)
			if other_user != user:
				room = find_or_create_private_chat(user, other_user)
				context["room"] = room
		except Account.DoesNotExist:
			pass

	# Passer la référence annonce au template (pour pré-remplir le message)
	if annonce_pk:
		try:
			from bazar.models import Annonce
			annonce = Annonce.objects.select_related('seller').prefetch_related('images').get(pk=annonce_pk)
			context["bazar_annonce"] = annonce
		except Exception:
			pass

	# 1. Find all the rooms this user is a part of 
	rooms1 = PrivateChatRoom.objects.filter(user1=user, is_active=True)
	rooms2 = PrivateChatRoom.objects.filter(user2=user, is_active=True)

	# 2. merge the lists
	rooms = list(chain(rooms1, rooms2))

	"""
	m_and_f:
		[{"message": "hey", "friend": "Mitch"}, {"message": "You there?", "friend": "Blake"},]
	Where message = The most recent message
	"""
	m_and_f = []
	for room in rooms:
		# Figure out which user is the "other user" (aka friend)
		if room.user1 == user:
			friend = room.user2
		else:
			friend = room.user1

		# Dernier message + compteur non-lu
		try:
			last_msg_obj = RoomChatMessage.objects.filter(room=room).latest('timestamp')
			last_msg = (last_msg_obj.content or '')[:30]
		except RoomChatMessage.DoesNotExist:
			last_msg = ""
		try:
			unread_obj = UnreadChatRoomMessages.objects.get(room=room, user=user)
			unread_count = unread_obj.count
		except UnreadChatRoomMessages.DoesNotExist:
			unread_count = 0

		m_and_f.append({
			'message': last_msg,
			'friend':  friend,
			'unread':  unread_count,
		})
	context['m_and_f'] = m_and_f

	context['debug'] = DEBUG
	context['debug_mode'] = settings.DEBUG
	return render(request, "chat/room.html", context)



# ── File upload endpoint ──────────────────────────────────────────────────────
@login_required(login_url="login")
@require_POST
def upload_chat_file(request):
    """
    Upload a file for the chat.
    Saves the file to RoomChatMessage and returns its URL + metadata.
    The client then broadcasts it through the WebSocket (send_file command).
    """
    room_id = request.POST.get('room_id')
    f = request.FILES.get('file')

    if not f:
        return JsonResponse({'error': 'Aucun fichier reçu.'}, status=400)
    if not room_id:
        return JsonResponse({'error': 'room_id manquant.'}, status=400)

    # Permission check
    try:
        room = PrivateChatRoom.objects.get(pk=room_id)
    except PrivateChatRoom.DoesNotExist:
        return JsonResponse({'error': 'Salon introuvable.'}, status=404)

    if request.user != room.user1 and request.user != room.user2:
        return JsonResponse({'error': 'Non autorisé.'}, status=403)

    # Determine file category
    mime = (f.content_type or '').split(';')[0].strip().lower()
    if mime in _IMAGE_TYPES:
        file_type = 'image'
    elif mime in _VIDEO_TYPES:
        file_type = 'video'
    else:
        file_type = 'document'

    # Enforce 25 MB max
    MAX_SIZE = 25 * 1024 * 1024
    if f.size > MAX_SIZE:
        return JsonResponse({'error': 'Fichier trop volumineux (max 25 Mo).'}, status=400)

    msg = RoomChatMessage.objects.create(
        user=request.user,
        room=room,
        content='',
        file=f,
        file_type=file_type,
    )

    return JsonResponse({
        'ok':        True,
        'file_url':  msg.file.url,
        'file_name': os.path.basename(f.name),
        'file_type': file_type,
        'msg_id':    msg.id,
    })


# ── Ajax call to return a private chatroom or create one if does not exist ────
def create_or_return_private_chat(request, *args, **kwargs):
	user1 = request.user
	payload = {}
	if user1.is_authenticated:
		if request.method == "POST":
			user2_id = request.POST.get("user2_id")
			try:
				user2 = Account.objects.get(pk=user2_id)
				chat = find_or_create_private_chat(user1, user2)
				payload['response'] = "Successfully got the chat."
				payload['chatroom_id'] = chat.id
			except Account.DoesNotExist:
				payload['response'] = "Unable to start a chat with that user."
	else:
		payload['response'] = "You can't start a chat if you are not authenticated."
	return HttpResponse(json.dumps(payload), content_type="application/json")


@login_required(login_url="login")
def send_story_reply(request):
    """
    POST /chat/story-reply/
    Params: story_author_id, message
    Crée ou récupère la room privée, insère le message, met à jour les non-lus.
    Retourne JSON {ok: true, chatroom_id: id}.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    from django.contrib.auth import get_user_model
    import django.utils.timezone as tz

    User = get_user_model()
    try:
        author_id = int(request.POST.get('story_author_id', 0))
        message   = request.POST.get('message', '').strip()[:500]
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'Invalid params'}, status=400)

    if not message:
        return JsonResponse({'ok': False, 'error': 'Empty message'}, status=400)
    if author_id == request.user.id:
        return JsonResponse({'ok': False, 'error': 'Cannot reply to own story'}, status=400)

    try:
        author = User.objects.get(pk=author_id)
    except User.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'User not found'}, status=404)

    # Trouver ou créer la room (bidirectionnel)
    room = PrivateChatRoom.objects.filter(
        user1=request.user, user2=author
    ).first() or PrivateChatRoom.objects.filter(
        user1=author, user2=request.user
    ).first()

    if not room:
        room = PrivateChatRoom.objects.create(
            user1=request.user,
            user2=author,
            is_active=False,
        )

    # Créer le message
    msg = RoomChatMessage.objects.create(
        user=request.user,
        room=room,
        content=message,
    )

    # Mettre à jour les non-lus pour le destinataire (auteur)
    try:
        unread, _ = UnreadChatRoomMessages.objects.get_or_create(
            room=room, user=author
        )
        unread.count += 1
        unread.most_recent_message = message[:500]
        unread.reset_timestamp = tz.now()
        unread.save(update_fields=['count', 'most_recent_message', 'reset_timestamp'])
    except Exception:
        pass  # non-bloquant

    return JsonResponse({'ok': True, 'chatroom_id': room.id, 'msg_id': msg.id})









@login_required(login_url="login")
def call_reject_push(request):
    """
    Appelé par le Service Worker quand l'utilisateur clique "Refuser" sur
    la push notification d'appel entrant (écran éteint ou app en arrière-plan).
    Envoie MSG_TYPE_CALL_REJECT au caller via le channel layer.
    """
    room_id = request.GET.get('room_id') or request.POST.get('room_id')
    if not room_id:
        return JsonResponse({'ok': False, 'error': 'room_id manquant'}, status=400)

    try:
        room = PrivateChatRoom.objects.get(pk=room_id)
    except PrivateChatRoom.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Room introuvable'}, status=404)

    # Identifier le caller (l'autre participant)
    caller = room.user1 if room.user2 == request.user else room.user2

    # Envoyer MSG_TYPE_CALL_REJECT au groupe personnel du caller
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{caller.id}",
            {
                "type":     "chat.call",
                "msg_type": MSG_TYPE_CALL_REJECT,
                "user_id":  request.user.id,
            }
        )
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)

    return JsonResponse({'ok': True})
