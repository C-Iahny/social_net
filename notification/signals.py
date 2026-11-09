from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Notification
from .realtime import push_counts, push_notification


@receiver(post_save, sender=Notification)
def _notification_saved(sender, instance, **kwargs):
    # Après commit : le consumer lit la base dans un autre thread/processus.
    transaction.on_commit(lambda: push_notification(instance))


@receiver(post_delete, sender=Notification)
def _notification_deleted(sender, instance, **kwargs):
    target_id = instance.target_id
    transaction.on_commit(lambda: push_counts(target_id))
