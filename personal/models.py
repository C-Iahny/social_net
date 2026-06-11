from django.db import models
from django.utils import timezone


# ──────────────────────────────────────────────────────────────
# Singleton : réglages de la section Hero (page Explore)
# ──────────────────────────────────────────────────────────────
class HeroSettings(models.Model):
    title         = models.CharField(
        max_length=200,
        default="Connectez-vous.\nPartagez. Grandissez.",
        verbose_name="Titre principal (H1)",
        help_text="Saut de ligne possible avec \\n — il sera affiché comme <br> dans le navigateur.",
    )
    subtitle      = models.TextField(
        default="Si vous connaissez ce que c'est Vazimba et que vous en êtes un(e), alors vous êtes au bon endroit car cette plateforme est conçue pour les Vazimba. Pour un partage d'idées, de messages et d'informations en temps réel.",
        verbose_name="Texte d'accroche",
    )
    gradient_from = models.CharField(
        max_length=20,
        default="#1877f2",
        verbose_name="Couleur de début (dégradé)",
        help_text="Code couleur hexadécimal, ex. #1877f2",
    )
    gradient_to   = models.CharField(
        max_length=20,
        default="#6c2bd9",
        verbose_name="Couleur de fin (dégradé)",
        help_text="Code couleur hexadécimal, ex. #6c2bd9",
    )
    background_image = models.ImageField(
        upload_to="hero_bg/",
        blank=True,
        null=True,
        verbose_name="Image de fond (optionnel)",
        help_text="Si renseignée, s'affiche derrière le dégradé (qui devient un calque semi-transparent).",
    )

    class Meta:
        verbose_name        = "Réglages du Hero"
        verbose_name_plural = "Réglages du Hero"

    def __str__(self):
        return "Réglages du Hero"

    # Singleton : toujours pk=1
    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    # Ne peut pas être supprimé depuis l'admin
    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get(cls):
        """Retourne l'unique instance, en la créant si besoin."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Announcement(models.Model):
    PRIORITY_CHOICES = [
        ('info',    '🔵 Info'),
        ('success', '🟢 Succès'),
        ('warning', '🟡 Avertissement'),
        ('danger',  '🔴 Urgent'),
    ]

    title       = models.CharField(max_length=200, verbose_name="Titre")
    content     = models.TextField(verbose_name="Contenu")
    priority    = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='info', verbose_name="Type")
    start_date  = models.DateTimeField(default=timezone.now, verbose_name="Date de début")
    end_date    = models.DateTimeField(null=True, blank=True, verbose_name="Date de fin (optionnel)")
    is_active   = models.BooleanField(default=True, verbose_name="Actif")
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = "Annonce"
        verbose_name_plural = "Annonces"

    def __str__(self):
        return f"[{self.get_priority_display()}] {self.title}"

    def is_visible(self):
        """Retourne True si l'annonce est active et dans sa période de diffusion."""
        now = timezone.now()
        if not self.is_active:
            return False
        if self.start_date > now:
            return False
        if self.end_date and self.end_date < now:
            return False
        return True


# PublicChatRoom et PublicRoomChatMessage sont définis dans public_chat/models.py
# Importer depuis là si besoin : from public_chat.models import PublicChatRoom, PublicRoomChatMessage
















