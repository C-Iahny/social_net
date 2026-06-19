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

from account.models import Account
from chat.models import PrivateChatRoom, RoomChatMessage
from chat.utils import find_or_create_private_chat

DEBUG = False

# ── MIME → file_type mapping ──────────────────────────────────────────────────
_IMAGE_TYPES = {'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
                'image/webp', 'image/bmp', 'image/tiff', 'image/heic', 'image/heif'}
_VIDEO_TYPES = {'video/mp4', 'video/webm', 'video/ogg', 'video/quicktime',
                'video/x-msvideo', 'video/x-matroska'}

def private_chat_room_view(request, *args, **kwargs):
	user = request.user
	room_id = request.GET.get("room_id")

	# Redirect them if not authenticated
	if not user.is_authenticated:
		return redirect("login")

	context = {}
	if room_id:
		room = PrivateChatRoom.objects.get(pk=room_id)
		context["room"] = room

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
		m_and_f.append({
			'message': "", # blank msg for now (since we have no messages)
			'friend': friend
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







