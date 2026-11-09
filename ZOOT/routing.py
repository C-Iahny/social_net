import os
import django

# Obligatoire : configurer Django AVANT d'importer des modèles ou consumers
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ZOOT.settings')
django.setup()


def _reset_chat_presence():
	"""
	Aucune connexion WebSocket ne survit à un redémarrage (déploiement Railway),
	mais la table `connected_users` des conversations, elle, gardait les
	participants « connectés » : leurs nouveaux messages n'étaient alors plus
	comptés comme non lus. On repart d'une présence vide à chaque démarrage.
	"""
	try:
		from chat.models import PrivateChatRoom
		PrivateChatRoom.connected_users.through.objects.all().delete()
	except Exception:
		pass  # base indisponible ou migrations pas encore passées


_reset_chat_presence()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path, re_path
from django.core.asgi import get_asgi_application

from chat.consumers import ChatConsumer
from public_chat.consumers import PublicChatConsumer
from notification.consumers import NotificationConsumer
from video.consumers import LiveConsumer

application = ProtocolTypeRouter({

	'http': get_asgi_application(),
	'websocket': AllowedHostsOriginValidator(
		AuthMiddlewareStack(
			URLRouter([
					path('', NotificationConsumer.as_asgi()),
					path('public_chat/<room_id>/', PublicChatConsumer.as_asgi()),
					path('chat/<room_id>/', ChatConsumer.as_asgi()),
					path('live/<room_id>/', LiveConsumer.as_asgi()),
			])
		)
	),
})



