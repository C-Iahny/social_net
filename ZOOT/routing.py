import os
import django

# Obligatoire : configurer Django AVANT d'importer des modèles ou consumers
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ZOOT.settings')
django.setup()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path, re_path
from django.core.asgi import get_asgi_application

from chat.consumers import ChatConsumer
from public_chat.consumers import PublicChatConsumer
from notification.consumers import NotificationConsumer

application = ProtocolTypeRouter({

	'http': get_asgi_application(),
	'websocket': AllowedHostsOriginValidator(
		AuthMiddlewareStack(
			URLRouter([

					path('', NotificationConsumer.as_asgi()),
					path('public_chat/<room_id>/', PublicChatConsumer.as_asgi()),
					path('chat/<room_id>/', ChatConsumer.as_asgi()),
			])
		)
	),
})



