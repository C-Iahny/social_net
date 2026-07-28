from django.db import models
from django.conf import settings
from django.urls import reverse
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

try:
    from ckeditor.fields import RichTextField
except ImportError:
    # Fallback si CKEditor n'est pas disponible
    RichTextField = models.TextField

from account.models import Account


# ── Continent / Country ───────────────────────────────────────────────────────
class Continent(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Country(models.Model):
    name      = models.CharField(max_length=100)
    continent = models.ForeignKey(Continent, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.name


# ── Tag ───────────────────────────────────────────────────────────────────────
class Tag(models.Model):
    label = models.CharField(max_length=64, unique=True)

    def __str__(self):
        return self.label


# ── Post ──────────────────────────────────────────────────────────────────────
class Post(models.Model):
    CATEGORY_CHOICES = [
        ('Category',      'Category'),
        ('Politics',      'Politics'),
        ('Sport',         'Sport'),
        ('Science',       'Science'),
        ('Tech',          'Tech'),
        ('Entertainment', 'Entertainment'),
        ('Travel',        'Travel'),
        ('Education',     'Education'),
        ('Humour',        'Humour'),
        ('Other',         'Other'),
    ]

    VIDEO_EXTS = {'mp4', 'webm', 'ogg', 'mov', 'mkv', 'avi', 'm4v', '3gp'}

    # ── Type de post ──────────────────────────────────────────────────────────
    DEFAULT = 'default'
    KABARY  = 'kabary'
    VINTANA = 'vintana'
    TYPE_CHOICES = [
        (DEFAULT, 'Post standard'),
        (KABARY,  'Kabary numérique'),
        (VINTANA, 'Capsule Vintana'),
    ]

    title        = models.CharField(max_length=255)
    header_image = models.ImageField(blank=True, null=True, upload_to='header_images')
    body         = RichTextField(blank=True, null=True)
    snippet      = models.CharField(max_length=255, blank=True, default='click the link above.')
    post_date    = models.DateField(auto_now_add=True)
    category     = models.CharField(max_length=255, blank=True, null=True, default='Category')
    file         = models.FileField(upload_to='files/', blank=True, null=True)
    video        = models.FileField(upload_to='videos/', blank=True, null=True)
    author       = models.ForeignKey(Account, on_delete=models.CASCADE)
    likes        = models.ManyToManyField(Account, blank=True, related_name='like_number')
    tags         = models.ManyToManyField(Tag, blank=True)
    group        = models.ForeignKey(
        'group.Group', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='posts'
    )
    is_pinned    = models.BooleanField(default=False, verbose_name='Épinglé')
    post_type    = models.CharField(
        max_length=10, choices=TYPE_CHOICES, default=DEFAULT,
        verbose_name='Type de post'
    )
    reveal_date  = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Date de révélation',
        help_text='Pour les Capsules Vintana : date à laquelle le contenu devient visible.',
    )
    region = models.CharField(
        max_length=30, blank=True, default='',
        verbose_name='Région',
        help_text='Région de Madagascar du post (auto-remplie depuis le profil de l\'auteur)',
        db_index=True,
    )

    # ── Statut & publication programmée ──────────────────────────────────────
    STATUS_PUBLISHED = 'published'
    STATUS_DRAFT     = 'draft'
    STATUS_SCHEDULED = 'scheduled'
    STATUS_CHOICES_POST = [
        (STATUS_PUBLISHED, 'Publié'),
        (STATUS_DRAFT,     'Brouillon'),
        (STATUS_SCHEDULED, 'Programmé'),
    ]
    status       = models.CharField(
        max_length=10, choices=STATUS_CHOICES_POST,
        default=STATUS_PUBLISHED, db_index=True,
        verbose_name='Statut',
    )
    scheduled_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Date de publication programmée',
        help_text='Laissez vide pour publier immédiatement.',
    )

    @property
    def is_locked(self):
        """Retourne True si c'est une capsule Vintana non encore révélée."""
        if self.post_type != Post.VINTANA:
            return False
        if self.reveal_date is None:
            return False
        from django.utils import timezone
        return timezone.now() < self.reveal_date

    def is_video(self):
        if self.header_image and self.header_image.name:
            ext = self.header_image.name.rsplit('.', 1)[-1].lower()
            return ext in self.VIDEO_EXTS
        return False

    def total_likes(self):
        return self.likes.count()

    @property
    def header_image_url(self):
        """Returns the header image URL (served by R2), or None."""
        if not self.header_image or not self.header_image.name:
            return None
        try:
            from django.core.files.storage import FileSystemStorage
            if isinstance(self.header_image.storage, FileSystemStorage):
                import os
                try:
                    if not os.path.exists(self.header_image.storage.path(self.header_image.name)):
                        return None
                except Exception:
                    return None
            return self.header_image.url
        except Exception:
            return None

    def __str__(self):
        return self.title + ' posted by ' + str(self.author)

    @property
    def get_cname(self):
        return "Post"

    def get_absolute_url(self):
        return reverse('post:post-detail', args=[self.pk])


# ── Comment ───────────────────────────────────────────────────────────────────
class Comment(models.Model):
    post       = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author     = models.ForeignKey(Account, on_delete=models.CASCADE)
    body       = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    parent     = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='replies'
    )

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.author} → {self.post} : {self.body[:40]}"


# ── Reaction ──────────────────────────────────────────────────────────────────
class Reaction(models.Model):
    REACTION_CHOICES = [
        ('like',  '👍'),
        ('heart', '❤️'),
        ('laugh', '😂'),
        ('wow',   '😮'),
        ('sad',   '😢'),
    ]
    post          = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reactions')
    user          = models.ForeignKey(Account, on_delete=models.CASCADE)
    reaction_type = models.CharField(max_length=10, choices=REACTION_CHOICES)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'user')

    def __str__(self):
        return f"{self.user} {self.reaction_type} → {self.post}"


# ── PostMedia ─────────────────────────────────────────────────────────────────
class PostMedia(models.Model):
    """Fichiers multiples attachés à un post (images + vidéos mélangés)."""
    IMAGE = 'image'
    VIDEO = 'video'
    TYPE_CHOICES = [(IMAGE, 'Image'), (VIDEO, 'Vidéo')]

    VIDEO_EXTS = {'mp4', 'webm', 'ogg', 'mov', 'mkv', 'avi', 'm4v', '3gp'}

    post       = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='media_files')
    file       = models.FileField(upload_to='post_media/')
    media_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=IMAGE)
    order      = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    @property
    def url(self):
        """Retourne l'URL du média (servi par R2)."""
        if not self.file or not self.file.name:
            return None
        try:
            from django.core.files.storage import FileSystemStorage
            if isinstance(self.file.storage, FileSystemStorage):
                import os
                try:
                    if not os.path.exists(self.file.storage.path(self.file.name)):
                        return None
                except Exception:
                    return None
            return self.file.url
        except Exception:
            return None

    @property
    def is_video(self):
        return self.media_type == self.VIDEO

    def __str__(self):
        return f"{self.media_type} #{self.order} → {self.post}"


# ── Follow ────────────────────────────────────────────────────────────────────
class Follow(models.Model):
    user          = models.ForeignKey(Account, on_delete=models.CASCADE,
                                      related_name='follower')
    user_follower = models.ForeignKey(Account, on_delete=models.CASCADE,
                                      related_name='be_follwed')

    def __str__(self):
        return f"{self.user_follower} follows {self.user}"


# ── Hashtag ───────────────────────────────────────────────────────────────────
class Hashtag(models.Model):
    tag   = models.CharField(max_length=64, unique=True)
    count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.tag

    class Meta:
        ordering = ['-count']


# ── Repost ────────────────────────────────────────────────────────────────────
class Repost(models.Model):
    """Republication d'un post par un utilisateur (comme un retweet)."""
    user       = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='reposts')
    post       = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reposts')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} reposted {self.post}"


# ── Signalement de contenu ────────────────────────────────────────────────────
class Report(models.Model):
    """Signalement générique (post, annonce, profil, etc.)"""

    REASON_SPAM     = 'spam'
    REASON_HATE     = 'hate'
    REASON_VIOLENCE = 'violence'
    REASON_NUDITY   = 'nudity'
    REASON_FALSE    = 'false'
    REASON_OTHER    = 'other'
    REASON_CHOICES = [
        (REASON_SPAM,     'Spam / publicité abusive'),
        (REASON_HATE,     'Discours haineux / harcelement'),
        (REASON_VIOLENCE, 'Violence / contenu choquant'),
        (REASON_NUDITY,   'Nudité / contenu adulte'),
        (REASON_FALSE,    'Fausse information'),
        (REASON_OTHER,    'Autre'),
    ]

    STATUS_PENDING   = 'pending'
    STATUS_REVIEWED  = 'reviewed'
    STATUS_DISMISSED = 'dismissed'
    STATUS_CHOICES = [
        (STATUS_PENDING,   'En attente'),
        (STATUS_REVIEWED,  'Traité'),
        (STATUS_DISMISSED, 'Rejeté'),
    ]

    reporter     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reports_sent',
        verbose_name='Signalé par',
    )
    content_type  = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id     = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    reason   = models.CharField(max_length=20, choices=REASON_CHOICES, verbose_name='Raison')
    comment  = models.TextField(blank=True, verbose_name='Commentaire')
    status   = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default=STATUS_PENDING, verbose_name='Statut',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Signalé le')
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='Traité le')

    class Meta:
        ordering = ['-created_at']
        unique_together = ('reporter', 'content_type', 'object_id')
        verbose_name = 'Signalement'
        verbose_name_plural = 'Signalements'

    def __str__(self):
        return f"{self.reporter} → {self.content_type} #{self.object_id} ({self.reason})"


# ── Post Bookmark (sauvegarder un post) ───────────────────────────────────────
class PostBookmark(models.Model):
    user       = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name='post_bookmarks',
    )
    post       = models.ForeignKey(
        Post, on_delete=models.CASCADE, related_name='bookmarks',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')
        ordering = ['-created_at']
        verbose_name = 'Post sauvegardé'
        verbose_name_plural = 'Posts sauvegardés'

    def __str__(self):
        return f"{self.user} ⊳ {self.post_id}"
