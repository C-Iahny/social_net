from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


def story_media_path(instance, filename):
    return f'stories/{instance.user.id}/{filename}'


def story_audio_path(instance, filename):
    return f'stories/audio/{instance.user.id}/{filename}'


STORY_TYPES = (
    ('image',       'Image'),
    ('video',       'Vidéo'),
    ('text',        'Texte seul'),
    ('image_text',  'Image + texte'),
)

BG_GRADIENTS = (
    ('grad_cyan',    'Cyan → Bleu'),
    ('grad_purple',  'Violet → Rose'),
    ('grad_sunset',  'Orange → Rose'),
    ('grad_forest',  'Vert → Cyan'),
    ('grad_night',   'Nuit → Violet'),
    ('grad_gold',    'Or → Orange'),
)


class Story(models.Model):
    user         = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='stories',
    )
    story_type   = models.CharField(max_length=12, choices=STORY_TYPES, default='image')

    # Média (photo ou vidéo — null pour les stories texte pur)
    media        = models.FileField(upload_to=story_media_path, blank=True, null=True)
    media_type   = models.CharField(max_length=8, blank=True, default='')  # 'image' | 'video'

    # Texte (caption pour image/vidéo, contenu principal pour text/image_text)
    caption      = models.CharField(max_length=200, blank=True, default='')

    # Apparence pour les stories texte
    bg_gradient  = models.CharField(
        max_length=20, choices=BG_GRADIENTS, default='grad_cyan', blank=True
    )
    text_align   = models.CharField(
        max_length=10,
        choices=(('left','Gauche'),('center','Centre'),('right','Droite')),
        default='center',
    )

    # Position libre du texte (pourcentage par rapport au cadre)
    text_x = models.FloatField(default=50.0, help_text='Position horizontale du texte (% depuis la gauche)')
    text_y = models.FloatField(default=50.0, help_text='Position verticale du texte (% depuis le haut)')
    text_color = models.CharField(max_length=20, blank=True, default='#ffffff', help_text='Couleur CSS du texte overlay')

    # Musique courte (optionnel — surtout pour les stories photo)
    audio           = models.FileField(upload_to=story_audio_path, blank=True, null=True)
    audio_type      = models.CharField(max_length=20, blank=True, default='')   # ex: 'audio/mpeg'
    audio_trim_start = models.FloatField(default=0.0, help_text='Début du clip (secondes)')

    # Lien promotionnel (pour les commerçants)
    link         = models.URLField(max_length=500, blank=True, default='')
    link_label   = models.CharField(max_length=60, blank=True, default='', verbose_name='Texte du bouton')

    created_at   = models.DateTimeField(auto_now_add=True)
    expires_at   = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Story'
        verbose_name_plural = 'Stories'

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        return timezone.now() < self.expires_at

    @property
    def time_left_seconds(self):
        delta = self.expires_at - timezone.now()
        return max(0, int(delta.total_seconds()))

    @property
    def view_count(self):
        return self.views.count()

    def __str__(self):
        return f'{self.user.username} — {self.story_type} ({self.created_at:%Y-%m-%d %H:%M})'


class StoryView(models.Model):
    story     = models.ForeignKey(Story, on_delete=models.CASCADE, related_name='views')
    viewer    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='story_views',
    )
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('story', 'viewer')
        ordering = ['-viewed_at']

    def __str__(self):
        return f'{self.viewer.username} → story#{self.story.id}'


# ── StoryReaction ────────────────────────────────────────────────────────────
class StoryReaction(models.Model):
    EMOJI_CHOICES = [
        ('❤️', 'Cœur'),
        ('😂', 'Haha'),
        ('😮', 'Wow'),
        ('😢', 'Triste'),
        ('🔥', 'Feu'),
    ]
    story    = models.ForeignKey(Story, on_delete=models.CASCADE, related_name='reactions')
    user     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='story_reactions',
    )
    emoji    = models.CharField(max_length=10, choices=EMOJI_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('story', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} {self.emoji} → story#{self.story.id}'


# ── StoryReply ────────────────────────────────────────────────────────────────
class StoryReply(models.Model):
    story      = models.ForeignKey(Story, on_delete=models.CASCADE, related_name='replies')
    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='story_replies',
    )
    message    = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} → story#{self.story.id}: {self.message[:40]}'
