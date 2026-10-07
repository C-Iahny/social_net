from django.db import models
from django.conf import settings


class LiveRoomQuerySet(models.QuerySet):
    def visible_to(self, user):
        """Exclut les lives de groupes privés dont `user` n'est pas membre."""
        from group.models import Group
        public = models.Q(group__isnull=True) | ~models.Q(group__privacy=Group.PRIVATE)
        if not getattr(user, 'is_authenticated', False):
            return self.filter(public)
        return self.filter(public | models.Q(group__memberships__user=user) | models.Q(host=user)).distinct()


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
    host_channel     = models.CharField(max_length=300, blank=True)
    viewer_count     = models.PositiveIntegerField(default=0)
    created_at       = models.DateTimeField(auto_now_add=True)
    ended_at         = models.DateTimeField(null=True, blank=True)
    replay_url       = models.URLField(max_length=500, blank=True, default='')
    replay_available = models.BooleanField(default=False)

    objects = LiveRoomQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.host.username} — {self.title} [{self.status}]"

    def can_view(self, user):
        """Un live de groupe privé n'est visible que des membres (et de l'hôte)."""
        if self.group_id is None or self.host_id == getattr(user, 'pk', None):
            return True
        from group.models import Group, GroupMembership
        if self.group.privacy != Group.PRIVATE:
            return True
        return (getattr(user, 'is_authenticated', False)
                and GroupMembership.objects.filter(group_id=self.group_id, user=user).exists())

    @property
    def get_cname(self):
        """Utilisé par le système de notification générale."""
        return "Live"
