from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import json


class Notification(models.Model):

	# Who the notification is sent to
	target 						= models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

	# The user that the creation of the notification was triggered by.
	from_user 					= models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="from_user")

	redirect_url				= models.URLField(max_length=500, null=True, unique=False, blank=True, help_text="The URL to be visited when a notification is clicked.")

	# statement describing the notification (ex: "Mitch sent you a friend request")
	verb 						= models.CharField(max_length=255, unique=False, blank=True, null=True)

	# When the notification was created/updated
	timestamp 					= models.DateTimeField(auto_now_add=True)

	# Some notifications can be marked as "read". (I used "read" instead of "active". I think its more appropriate)
	read 						= models.BooleanField(default=False, db_index=True)

	# A generic type that can refer to a FriendRequest, Unread Message, or any other type of "Notification"
	# See article: https://simpleisbetterthancomplex.com/tutorial/2016/10/13/how-to-use-generic-relations.html
	content_type 				= models.ForeignKey(ContentType, on_delete=models.CASCADE)
	object_id 					= models.PositiveIntegerField()
	content_object 				= GenericForeignKey()

	def __str__(self):
		return self.verb

	def get_content_object_type(self):
		return str(self.content_object.get_cname)


# ─────────────────────────────────────────────────────────────
# Web Push Subscription
# ─────────────────────────────────────────────────────────────
class PushSubscription(models.Model):
    user     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_subscriptions',
    )
    endpoint = models.TextField(unique=True)
    p256dh   = models.TextField()   # public key
    auth     = models.TextField()   # auth secret
    created  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Push Subscription'

    def __str__(self):
        return f"{self.user} — {self.endpoint[:60]}"

    def as_subscription_info(self):
        return {
            'endpoint': self.endpoint,
            'keys': {
                'p256dh': self.p256dh,
                'auth':   self.auth,
            }
        }

    @classmethod
    def send_notification(cls, user, title, body, url='/', icon='/static/icon-192.png'):
        """Envoie une push notification à tous les appareils de l'utilisateur."""
        import json
        from django.conf import settings as cfg

        if not cfg.VAPID_PUBLIC_KEY or not cfg.VAPID_PRIVATE_KEY:
            return  # Push non configuré

        try:
            from pywebpush import webpush, WebPushException
        except ImportError:
            return

        payload = json.dumps({'title': title, 'body': body, 'url': url, 'icon': icon})
        vapid_claims = {'sub': f"mailto:{cfg.VAPID_CLAIMS_EMAIL}"}

        for sub in cls.objects.filter(user=user):
            try:
                webpush(
                    subscription_info=sub.as_subscription_info(),
                    data=payload,
                    vapid_private_key=cfg.VAPID_PRIVATE_KEY,
                    vapid_claims=vapid_claims,
                )
            except Exception:
                # Subscription expirée ou invalide → la supprimer
                sub.delete()

    @classmethod
    def send_call_notification(cls, callee, caller_name, caller_image, room_id, call_mode='video'):
        """
        Envoie une push notification d'appel entrant.
        Le SW affichera la notification même écran éteint, avec sonnerie système
        et boutons Répondre / Refuser.
        """
        import json
        from django.conf import settings as cfg

        if not cfg.VAPID_PUBLIC_KEY or not cfg.VAPID_PRIVATE_KEY:
            return

        try:
            from pywebpush import webpush, WebPushException
        except ImportError:
            return

        icon = caller_image or '/static/logo/vazimba_v2_icon.png'
        mode_label = 'audio' if call_mode == 'audio' else 'vidéo'
        payload = json.dumps({
            'type':        'incoming_call',
            'title':       f'📞 {caller_name}',
            'body':        f'Appel {mode_label} entrant',
            'icon':        icon,
            'url':         f'/chat/?room_id={room_id}&auto_answer=1&call_mode={call_mode}',
            'room_id':     str(room_id),
            'call_mode':   call_mode,
            'caller_name': caller_name,
        })
        vapid_claims = {'sub': f"mailto:{cfg.VAPID_CLAIMS_EMAIL}"}

        subs = list(cls.objects.filter(user=callee))
        for sub in subs:
            try:
                webpush(
                    subscription_info=sub.as_subscription_info(),
                    data=payload,
                    vapid_private_key=cfg.VAPID_PRIVATE_KEY,
                    vapid_claims=vapid_claims,
                )
            except Exception:
                sub.delete()

