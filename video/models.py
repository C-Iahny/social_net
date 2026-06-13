from django.db import models
from django.conf import settings


class LiveRoom(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_ENDED  = 'ended'
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('ended',  'Ended'),
    ]

    host         = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='live_rooms_hosted',
    )
    title        = models.CharField(max_length=200)
    status       = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    group        = models.ForeignKey(
        'group.Group',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='live_rooms',
    )
    # Django Channels channel_name of the host's WebSocket — used for direct signaling
    host_channel  = models.CharField(max_length=300, blank=True)
    viewer_count  = models.PositiveIntegerField(default=0)
    created_at    = models.DateTimeField(auto_now_add=True)
    ended_at      = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.host.username} — {self.title} [{self.status}]"
