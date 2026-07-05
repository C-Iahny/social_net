from django.core.serializers.python import Serializer
from django.contrib.humanize.templatetags.humanize import naturaltime


class LazyNotificationEncoder(Serializer):
	"""
	Serialize a Notification into JSON.
	There are 4 types
		1. FriendRequest
		2. FriendList
		3. UnreadChatRoomMessage
		4. Post (like/comment/repost)
	"""
	def get_dump_object(self, obj):
		dump_object = {}
		# Guard: if the linked object was deleted, content_object is None.
		# Skip gracefully to avoid crashing the entire serialization batch.
		try:
			ctype = obj.get_content_object_type()
		except Exception:
			return dump_object  # Return empty dict; filtered out downstream.
		if ctype == "FriendRequest":
			try:
				is_active = str(obj.content_object.is_active)
			except Exception:
				is_active = 'False'
			dump_object.update({'notification_type': ctype})
			dump_object.update({'notification_id': str(obj.pk)})
			dump_object.update({'verb': obj.verb})
			dump_object.update({'is_active': is_active})
			dump_object.update({'is_read': str(obj.read)})
			dump_object.update({'natural_timestamp': str(naturaltime(obj.timestamp))})
			dump_object.update({'timestamp': str(obj.timestamp)})
			dump_object.update({
				'actions': {
					'redirect_url': str(obj.redirect_url) if obj.redirect_url else '/',
				},
				"from": {
					"image_url": str(obj.from_user.profile_image.url) if obj.from_user else ''
				}
			})
		if ctype == "FriendList":
			dump_object.update({'notification_type': ctype})
			dump_object.update({'notification_id': str(obj.pk)})
			dump_object.update({'verb': obj.verb})
			dump_object.update({'natural_timestamp': str(naturaltime(obj.timestamp))})
			dump_object.update({'is_read': str(obj.read)})
			dump_object.update({'timestamp': str(obj.timestamp)})
			dump_object.update({
				'actions': {
					'redirect_url': str(obj.redirect_url) if obj.redirect_url else '/',
				},
				"from": {
					"image_url": str(obj.from_user.profile_image.url) if obj.from_user else ''
				}
			})
		if ctype == "UnreadChatRoomMessages":
			dump_object.update({'notification_type': ctype})
			dump_object.update({'notification_id': str(obj.pk)})
			dump_object.update({'verb': obj.verb})
			dump_object.update({'natural_timestamp': str(naturaltime(obj.timestamp))})
			dump_object.update({'timestamp': str(obj.timestamp)})
			try:
				other = obj.content_object.get_other_user
				from_img = str(other.profile_image.url)
				from_title = str(other.username)
			except Exception:
				from_img = ''
				from_title = ''
			dump_object.update({
				'actions': {
					'redirect_url': str(obj.redirect_url) if obj.redirect_url else '/',
				},
				"from": {
					"title": from_title,
					"image_url": from_img,
				}
			})
		if ctype == "Post":
			dump_object.update({'notification_type': 'Post'})
			dump_object.update({'notification_id': str(obj.pk)})
			dump_object.update({'verb': obj.verb})
			dump_object.update({'natural_timestamp': str(naturaltime(obj.timestamp))})
			dump_object.update({'timestamp': str(obj.timestamp)})
			dump_object.update({'is_read': str(obj.read)})
			dump_object.update({
				'actions': {
					'redirect_url': str(obj.redirect_url) if obj.redirect_url else '/',
				},
				"from": {
					"image_url": str(obj.from_user.profile_image.url) if obj.from_user else '',
				}
			})

		return dump_object