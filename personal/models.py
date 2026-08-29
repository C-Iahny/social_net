from django.db import models
from django.utils import timezone


# ──────────────────────────────────────────────────────────────
# Singleton : réglages de la section Hero (page Explore)
# ──────────────────────────────────────────────────────────────
class HeroSettings(models.Model):
    title         = models.CharField(
        max_length=200,
        default="Le réseau social qui parle *malagasy*.",
        verbose_name="Titre principal (H1)",
        help_text=(
            "Saut de ligne possible avec \\n. "
            "Un mot entre *astérisques* s'affiche dans le serif italique de la "
            "charte — par exemple : Le réseau social qui parle *malagasy*."
        ),
    )
    subtitle      = models.TextField(
        default="Un fil d'actualité, une place de marché et un guide du pays — au même endroit.",
        verbose_name="Texte d'accroche",
        help_text="Une phrase, affichée sous le titre. Les phrases courtes rendent mieux.",
    )
    # Défauts alignés sur la charte acajou/ambre du reste de l'interface
    # (--accent #8B4513 dans snippets/base_css.html). Les anciens défauts
    # étaient l'indigo/violet #1877f2 → #6c2bd9, hérités d'une charte
    # abandonnée : le hero jurait avec la page qui l'entoure.
    gradient_from = models.CharField(
        max_length=20,
        default="#5c2a08",
        verbose_name="Couleur de début (dégradé)",
        help_text="Code couleur hexadécimal, ex. #5c2a08",
    )
    gradient_to   = models.CharField(
        max_length=20,
        default="#A0522D",
        verbose_name="Couleur de fin (dégradé)",
        help_text="Code couleur hexadécimal, ex. #A0522D",
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
















