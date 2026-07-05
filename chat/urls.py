from django.urls import path

from chat.views import (
	private_chat_room_view,
	create_or_return_private_chat,
	upload_chat_file,
	send_story_reply,
	call_reject_push,
	get_ice_servers,
)

app_name = 'chat'

urlpatterns = [
	path('',                           private_chat_room_view,         name='private-chat-room'),
	path('create_or_return_private_chat', create_or_return_private_chat, name='create-or-return-private-chat'),
	path('upload_file/',               upload_chat_file,               name='upload-chat-file'),
	path('story-reply/',               send_story_reply,               name='story_reply'),
	path('call-reject-push/',          call_reject_push,               name='call-reject-push'),
	path('ice-servers/',               get_ice_servers,                name='ice-servers'),
]