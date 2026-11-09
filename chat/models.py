from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse

from notification.models import Notification

class PrivateChatRoom(models.Model):
	"""
	A private room for people to chat in.
	"""
	user1               = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user1")
	user2               = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user2")

	# Users who are currently connected to the socket (Used to keep track of unread messages)
	connected_users     = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="connected_users")

	is_active 			= models.BooleanField(default=False)

	def connect_user(self, user):
		"""
		return true if user is added to the connected_users list
		"""
		is_user_added = False
		if not user in self.connected_users.all():
			self.connected_users.add(user)
			is_user_added = True
		return is_user_added 


	def disconnect_user(self, user):
		"""
		return true if user is removed from connected_users list
		"""
		is_user_removed = False
		if user in self.connected_users.all():
			self.connected_users.remove(user)
			is_user_removed = True
		return is_user_removed

	@property
	def group_name(self):
		"""
		Returns the Channels Group name that sockets should subscribe to to get sent
		messages as they are generated.
		"""
		return f"PrivateChatRoom-{self.id}"


class RoomChatMessageManager(models.Manager):
	def by_room(self, room):
		# Auteur, message cité et réactions chargés avec la page : l'encodeur
		# faisait ~3 requêtes par message à chaque ouverture d'une conversation.
		from django.db.models import Prefetch
		qs = (RoomChatMessage.objects.filter(room=room)
			.select_related('user', 'reply_to', 'reply_to__user')
			.prefetch_related(Prefetch('reactions', queryset=MessageReaction.objects.select_related('user')))
			.order_by("-timestamp"))
		return qs

class RoomChatMessage(models.Model):
	"""
	Chat message created by a user inside a Room.
	Can be a text message, a file attachment, or both.
	"""
	user      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
	room      = models.ForeignKey(PrivateChatRoom, on_delete=models.CASCADE)
	timestamp = models.DateTimeField(auto_now_add=True)
	content   = models.TextField(unique=False, blank=True, default='')

	# ── File attachment ──────────────────────────────────────────────────────
	file      = models.FileField(upload_to='chat_files/', blank=True, null=True)
	# 'image' | 'video' | 'document' | '' (text-only)
	file_type = models.CharField(max_length=20, blank=True, default='')

	# ── Reply (citation) ─────────────────────────────────────────────────────
	reply_to  = models.ForeignKey(
		'self', on_delete=models.SET_NULL, null=True, blank=True,
		related_name='replies'
	)

	objects = RoomChatMessageManager()

	class Meta:
		indexes = [models.Index(fields=['room', 'timestamp'], name='chatmsg_room_time_idx')]

	def __str__(self):
		if self.file:
			return f'[{self.file_type or "file"}] {self.file.name}'
		return self.content[:80]


class MessageReaction(models.Model):
	"""
	Réaction emoji sur un message de chat.
	Un seul emoji par utilisateur par message (style WhatsApp).
	"""
	message = models.ForeignKey(
		RoomChatMessage, on_delete=models.CASCADE, related_name='reactions'
	)
	user  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
	emoji = models.CharField(max_length=10)

	class Meta:
		unique_together = ('message', 'user')

	def __str__(self):
		return f'{self.emoji} par {self.user.username} sur msg {self.message_id}'



class UnreadChatRoomMessages(models.Model):
	"""
	Keep track of the number of unread messages by a specific user in a specific private chat.
	When the user connects the chat room, the messages will be considered "read" and 'count' will be set to 0.
	"""
	room                = models.ForeignKey(PrivateChatRoom, on_delete=models.CASCADE, related_name="room")

	user                = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

	count               = models.IntegerField(default=0)

	most_recent_message = models.CharField(max_length=500, blank=True, null=True)

	# last time msgs were read by the user
	reset_timestamp     = models.DateTimeField()

	notifications       = GenericRelation(Notification)


	def __str__(self):
		return f"Messages that {str(self.user.username)} has not read yet."

	def save(self, *args, **kwargs):
		if not self.id: # if just created, add a timestamp. Otherwise do not automatically change it ever.
			self.reset_timestamp = timezone.now()
		return super(UnreadChatRoomMessages, self).save(*args, **kwargs)

	@property
	def get_cname(self):
		"""
		For determining what kind of object is associated with a Notification
		"""
		return "UnreadChatRoomMessages"

	@property
	def get_other_user(self):
		"""
		Get the other user in the chat room
		"""
		if self.user == self.room.user1:
			return self.room.user2
		else:
			return self.room.user1


@receiver(post_save, sender=PrivateChatRoom)
def create_unread_chatroom_messages_obj(sender, instance, created, **kwargs):
	if created:
		unread_msgs1 = UnreadChatRoomMessages(room=instance, user=instance.user1)
		unread_msgs1.save()

		unread_msgs2 = UnreadChatRoomMessages(room=instance, user=instance.user2)
		unread_msgs2.save()



@receiver(pre_save, sender=UnreadChatRoomMessages)
def _stash_previous_count(sender, instance, **kwargs):
	"""Mémorise le compteur en base avant écriture (lu par le post_save ci-dessous)."""
	instance._prev_count = None
	if instance.id is not None:
		instance._prev_count = (UnreadChatRoomMessages.objects
			.filter(id=instance.id).values_list('count', flat=True).first())


@receiver(post_save, sender=UnreadChatRoomMessages)
def sync_unread_notification(sender, instance, created, **kwargs):
	"""
	Tient la notification « message non lu » de la cloche en phase avec le compteur :
	- compteur à zéro (conversation ouverte) → plus aucune notification, doublons compris ;
	- compteur qui monte → notification créée ou rafraîchie (texte, date).
	En post_save, la ligne est déjà écrite : la diffusion temps réel
	(notification/signals.py) lit donc le bon compteur.
	"""
	content_type = ContentType.objects.get_for_model(instance)
	existing = Notification.objects.filter(
		target=instance.user, content_type=content_type, object_id=str(instance.id))
	if instance.count == 0:
		if created:
			return
		existing.delete()
		return
	prev = getattr(instance, '_prev_count', None)
	if prev is not None and prev >= instance.count:
		return
	other_user = instance.room.user2 if instance.user_id == instance.room.user1_id else instance.room.user1
	notification = existing.first()
	if notification is not None:
		notification.verb = instance.most_recent_message
		notification.timestamp = timezone.now()
		notification.from_user = other_user
		notification.save()
	else:
		instance.notifications.create(
			target=instance.user,
			from_user=other_user,
			redirect_url=reverse('chat:private-chat-room') + f'?room_id={instance.room.id}',
			verb=instance.most_recent_message,
			content_type=content_type,
		)


def reset_unread(room, user):
	"""
	Remet à zéro les non-lus de `user` dans `room` (ouverture de la conversation).
	Le signal ci-dessus supprime alors la notification de la cloche « Messages ».
	"""
	unread, _ = UnreadChatRoomMessages.objects.get_or_create(room=room, user_id=user.id)
	if unread.count != 0 or unread.notifications.exists():
		unread.count = 0
		unread.save()
	return unread













