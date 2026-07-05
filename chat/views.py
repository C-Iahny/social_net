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
from chat.constants import MSG_TYPE_CALL_REJECT, MSG_TYPE_UNREAD_NOTIF

DEBUG = False

# ── MIME → file_type mapping ──────────────────────────────────────────────────
_IMAGE_TYPES = {'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
                'image/webp', 'image/bmp', 'image/tiff', 'image/heic', 'image/heif'}
_VIDEO_TYPES = {'video/mp4', 'video/webm', 'video/ogg', 'video/quicktime',
                'video/x-msvideo', 'video/x-matroska'}
_AUDIO_TYPES = {'audio/webm', 'audio/ogg', 'audio/mp4', 'audio/mpeg',
                'audio/wav', 'audio/aac', 'audio/x-m4a', 'audio/3gpp',
                'audio/3gpp2', 'audio/amr'}

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
    elif mime in _AUDIO_TYPES or mime.startswith('audio/'):
        file_type = 'voice'
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

    file_name = os.path.basename(f.name)
    file_url  = msg.file.url

    # ── Broadcast immédiat via channel layer ──────────────────────────────────
    # Évite le 2ème aller-retour client → WS consumer : le destinataire voit
    # le message dès que l'upload est terminé côté serveur, sans délai WS.
    broadcast_done = False
    try:
        channel_layer = get_channel_layer()
        preview = '[🎤 vocal]' if file_type == 'voice' else f'[📎 {file_name}]'

        # Incrémenter non-lus pour l'autre utilisateur s'il n'est pas dans la room
        other = room.user2 if request.user == room.user1 else room.user1
        connected_ids = set(room.connected_users.values_list('id', flat=True))
        unread_count = None
        if other.id not in connected_ids:
            unread_obj, _ = UnreadChatRoomMessages.objects.get_or_create(
                room=room, user=other
            )
            unread_obj.count += 1
            unread_obj.most_recent_message = preview
            unread_obj.save(update_fields=['count', 'most_recent_message'])
            unread_count = unread_obj.count

        # Broadcast du fichier à tous les membres de la room
        async_to_sync(channel_layer.group_send)(
            room.group_name,
            {
                "type":          "chat.file",
                "profile_image": request.user.profile_image.url,
                "username":      request.user.username,
                "user_id":       request.user.id,
                "msg_id":        msg.id,
                "file_url":      file_url,
                "file_name":     file_name,
                "file_type":     file_type,
            }
        )

        # Notifier le badge non-lu si l'autre user n'est pas connecté
        if unread_count is not None:
            async_to_sync(channel_layer.group_send)(
                f"user_{other.id}",
                {
                    "type":         "chat.unread_notif",
                    "msg_type":     MSG_TYPE_UNREAD_NOTIF,
                    "from_user_id": request.user.id,
                    "count":        unread_count,
                }
            )

        broadcast_done = True
    except Exception as e:
        # Fallback : le client enverra la commande WS manuellement
        print(f"[upload_chat_file] broadcast error: {e}")

    return JsonResponse({
        'ok':        True,
        'file_url':  file_url,
        'file_name': file_name,
        'file_type': file_type,
        'msg_id':    msg.id,
        'broadcast': broadcast_done,  # True = client n'a PAS besoin d'envoyer via WS
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
def get_ice_servers(request):
    """
    Retourne les serveurs ICE (STUN + TURN) pour WebRTC.
    Si METERED_API_KEY + METERED_APP_ID sont définis en variable d'env,
    retourne des credentials temporaires Metered.ca (TURN mondial fiable, 50 GB/mois gratuit).
    Sinon, fallback vers l'open relay communautaire (moins fiable sur mobile 4G/CGNAT).

    Pour activer Metered.ca gratuit :
    1. Créer un compte sur https://app.metered.ca
    2. Créer une app, récupérer l'App ID et l'API Key
    3. Sur Railway : ajouter METERED_API_KEY=<clé> et METERED_APP_ID=<id_app>
    """
    import requests as _r

    stun_urls = [
        "stun:stun.l.google.com:19302",
        "stun:stun1.l.google.com:19302",
        "stun:stun.cloudflare.com:3478",
        "stun:stun.relay.metered.ca:80",
    ]
    servers = [{"urls": stun_urls}]

    api_key = os.environ.get('METERED_API_KEY', '')
    app_id  = os.environ.get('METERED_APP_ID', '')

    if api_key and app_id:
        try:
            resp = _r.get(
                f"https://{app_id}.metered.ca/api/v1/turn/credentials",
                params={"apiKey": api_key},
                timeout=3
            )
            if resp.ok:
                turn_list = resp.json()
                if isinstance(turn_list, list) and turn_list:
                    servers.extend(turn_list)
                    return JsonResponse({"iceServers": servers, "source": "metered"})
        except Exception:
            pass  # fall through to open relay

    # Fallback : plusieurs TURN publics communautaires (ordre de fiabilité décroissant)
    # freestun.net = serveur européen, souvent plus accessible depuis Madagascar
    # openrelay.metered.ca = communauté US, souvent surchargé/bloqué
    servers.extend([
        {
            "urls": ["turn:freestun.net:3479", "turns:freestun.net:5350"],
            "username": "free",
            "credential": "free"
        },
        {
            "urls": [
                "turn:openrelay.metered.ca:443",
                "turns:openrelay.metered.ca:443?transport=tcp"
            ],
            "username": "openrelayproject",
            "credential": "openrelayproject"
        }
    ])
    return JsonResponse({"iceServers": servers, "source": "community-fallback"})


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
