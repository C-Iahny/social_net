from django.db import models
from django.utils.text import slugify
from account.models import Account


class Group(models.Model):
    PUBLIC  = 'public'
    PRIVATE = 'private'
    PRIVACY_CHOICES = [(PUBLIC, 'Public'), (PRIVATE, 'Privé')]

    # ── Catégories thématiques ────────────────────────────────────
    CAT_SPORT      = 'sport'
    CAT_MUSIQUE    = 'musique'
    CAT_CUISINE    = 'cuisine'
    CAT_TECH       = 'tech'
    CAT_ART        = 'art'
    CAT_EDUCATION  = 'education'
    CAT_VOYAGE     = 'voyage'
    CAT_BUSINESS   = 'business'
    CAT_GAMING     = 'gaming'
    CAT_BIENETRE   = 'bienetre'
    CAT_NATURE     = 'nature'
    CAT_HUMOUR     = 'humour'
    CAT_MADAGASCAR = 'madagascar'
    CAT_FAMILLE    = 'famille'
    CAT_RELIGION   = 'religion'
    CAT_AUTRE      = 'autre'
    CATEGORY_CHOICES = [
        (CAT_SPORT,      '🏃 Sport'),
        (CAT_MUSIQUE,    '🎵 Musique'),
        (CAT_CUISINE,    '🍳 Cuisine'),
        (CAT_TECH,       '💻 Technologie'),
        (CAT_ART,        '🎨 Art & Culture'),
        (CAT_EDUCATION,  '📚 Éducation'),
        (CAT_VOYAGE,     '✈️ Voyage'),
        (CAT_BUSINESS,   '💼 Business'),
        (CAT_GAMING,     '🎮 Gaming'),
        (CAT_BIENETRE,   '🧘 Bien-être'),
        (CAT_NATURE,     '🌱 Nature'),
        (CAT_HUMOUR,     '😄 Humour'),
        (CAT_MADAGASCAR, '🇲🇬 Madagascar'),
        (CAT_FAMILLE,    '👨‍👩‍👧 Famille'),
        (CAT_RELIGION,   '🙏 Religion & Spiritualité'),
        (CAT_AUTRE,      '💬 Autre'),
    ]

    name        = models.CharField(max_length=100)
    slug        = models.SlugField(max_length=110, unique=True, blank=True)
    description = models.TextField(max_length=500, blank=True)
    cover       = models.ImageField(upload_to='group_covers/', blank=True, null=True)
    creator     = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='created_groups')
    members     = models.ManyToManyField(Account, through='GroupMembership', related_name='joined_groups', blank=True)
    privacy     = models.CharField(max_length=10, choices=PRIVACY_CHOICES, default=PUBLIC)
    category    = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, blank=True, default='',
        verbose_name='Catégorie', db_index=True,
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    dina        = models.TextField(
        blank=True, default='',
        verbose_name='Dina',
        help_text='Charte communautaire du groupe (règles, engagements, traditions)',
    )

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
    ADMIN     = 'admin'
    MODERATOR = 'moderator'
    MEMBER    = 'member'
    ROLE_CHOICES = [
        (ADMIN,     'Admin'),
        (MODERATOR, 'Modérateur'),
        (MEMBER,    'Membre'),
    ]

    user       = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='group_memberships')
    group      = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='memberships')
    role       = models.CharField(max_length=12, choices=ROLE_CHOICES, default=MEMBER)
    joined_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'group')
        ordering = ['-joined_at']

    def __str__(self):
        return f"{self.user} — {self.group} ({self.role})"

    @property
    def is_admin(self):
        return self.role == self.ADMIN

    @property
    def is_moderator(self):
        return self.role in (self.ADMIN, self.MODERATOR)


class GroupEvent(models.Model):
    group       = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='events')
    organizer   = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='organized_events')
    title       = models.CharField(max_length=150, verbose_name='Titre')
    description = models.TextField(max_length=1000, blank=True, verbose_name='Description')
    location    = models.CharField(max_length=200, blank=True, verbose_name='Lieu')
    event_date  = models.DateTimeField(verbose_name="Date de l'événement")
    created_at  = models.DateTimeField(auto_now_add=True)
    attendees   = models.ManyToManyField(Account, blank=True, related_name='attending_events')

    class Meta:
        ordering = ['event_date']

    def __str__(self):
        return f"{self.title} — {self.group.name}"
