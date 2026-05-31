from django.db import models
from django.utils.text import slugify
from account.models import Account


class Group(models.Model):
    PUBLIC  = 'public'
    PRIVATE = 'private'
    PRIVACY_CHOICES = [(PUBLIC, 'Public'), (PRIVATE, 'Privé')]

    name        = models.CharField(max_length=100)
    slug        = models.SlugField(max_length=110, unique=True, blank=True)
    description = models.TextField(max_length=500, blank=True)
    cover       = models.ImageField(upload_to='group_covers/', blank=True, null=True)
    creator     = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='created_groups')
    members     = models.ManyToManyField(Account, through='GroupMembership', related_name='joined_groups', blank=True)
    privacy     = models.CharField(max_length=10, choices=PRIVACY_CHOICES, default=PUBLIC)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or 'group'
            slug = base
            i = 1
            while Group.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('group:detail', args=[self.slug])

    @property
    def member_count(self):
        return self.members.count()

    @property
    def cover_url(self):
        if not self.cover or not self.cover.name:
            return None
        try:
            from django.core.files.storage import FileSystemStorage
            if isinstance(self.cover.storage, FileSystemStorage):
                import os
                if not os.path.exists(self.cover.storage.path(self.cover.name)):
                    return None
            return self.cover.url
        except Exception:
            return None


class GroupMembership(models.Model):
    ADMIN  = 'admin'
    MEMBER = 'member'
    ROLE_CHOICES = [(ADMIN, 'Admin'), (MEMBER, 'Membre')]

    user       = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='group_memberships')
    group      = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='memberships')
    role       = models.CharField(max_length=10, choices=ROLE_CHOICES, default=MEMBER)
    joined_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'group')
        ordering = ['-joined_at']

    def __str__(self):
        return f"{self.user} — {self.group} ({self.role})"
