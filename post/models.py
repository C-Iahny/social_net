from django.db import models
from django.utils import timezone
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse

from account.models import Account


# ── Tags ──────────────────────────────────────────────────────────────────────
class Tag(models.Model):
    label = models.CharField(max_length=64, unique=True)

    def __str__(self):
        return self.label


# ── Post ──────────────────────────────────────────────────────────────────────
class Post(models.Model):
    CATEGORY_CHOICES = [
        ('Category', 'Category'),
        ('Politics', 'Politics'),
        ('Sport', 'Sport'),
        ('Science', 'Science'),
        ('Tech', 'Tech'),
        ('Entertainment', 'Entertainment'),
        ('Travel', 'Travel'),
        ('Education', 'Education'),
        ('Humour', 'Humour'),
        ('Other', 'Other'),
    ]

    VIDEO_EXTS = {'mp4', 'webm', 'ogg', 'mov', 'mkv', 'avi', 'm4v', '3gp'}

    title        = models.CharField(max_length=50, null=True, blank=True)
    body         = models.TextField(max_length=10000, null=True, blank=True)
    image        = models.ImageField(upload_to='post_images', null=True, blank=True)
    header_image = models.ImageField(blank=True, null=True, upload_to="header_images")
    post_date    = models.DateTimeField(auto_now_add=True)
    author       = models.ForeignKey(Account, on_delete=models.CASCADE)
    likes        = models.ManyToManyField(Account, blank=True, related_name='post_likes')
    tags         = models.ManyToManyField(Tag, blank=True)
    category     = models.CharField(max_length=50, choices=CATEGORY_CHOICES,
                                    default='Category')
    file         = models.FileField(upload_to='post_files/', null=True, blank=True)

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
        ('like',   '👍'),
        ('heart',  '❤️'),
        ('laugh',  '😂'),
        ('wow',    '😮'),
        ('sad',    '😢'),
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
                                      related_name='following')
    user_follower = models.ForeignKey(Account, on_delete=models.CASCADE,
                                      related_name='followers')

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


# ── Continent / Country (legacy) ──────────────────────────────────────────────
class Continent(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Country(models.Model):
    name      = models.CharField(max_length=100)
    continent = models.ForeignKey(Continent, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.name
