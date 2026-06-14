from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Annonce(models.Model):
    """
    Annonce du Bazar Vazimba — petites annonces entre particuliers.
    Chaque annonce appartient à un vendeur (Account) et peut avoir plusieurs photos.
    """

    # ── Catégories ─────────────────────────────────────────────────────────────
    CATEGORY_CHOICES = [
        ('electronique',    _('Électronique & Téléphones')),
        ('vehicules',       _('Véhicules & Motos')),
        ('immobilier',      _('Immobilier & Location')),
        ('mode',            _('Mode & Vêtements')),
        ('maison',          _('Maison & Mobilier')),
        ('agriculture',     _('Agriculture & Élevage')),
        ('alimentaire',     _('Alimentaire & Boissons')),
        ('services',        _('Services & Prestations')),
        ('emploi',          _('Emploi & Formation')),
        ('artisanat',       _('Artisanat & Art')),
        ('sports',          _('Sports & Loisirs')),
        ('bebe',            _('Bébé & Enfants')),
        ('autres',          _('Autres')),
    ]

    # ── État du produit ────────────────────────────────────────────────────────
    CONDITION_CHOICES = [
        ('neuf',        _('Neuf')),
        ('tres_bon',    _('Très bon état')),
        ('bon',         _('Bon état')),
        ('correct',     _('État correct')),
        ('pieces',      _('Pour pièces')),
    ]

    # ── Statut de l'annonce ────────────────────────────────────────────────────
    STATUS_CHOICES = [
        ('active',  _('Active')),
        ('vendue',  _('Vendue')),
        ('pause',   _('En pause')),
        ('expiree', _('Expirée')),
    ]

    # ── Champs principaux ──────────────────────────────────────────────────────
    seller      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='annonces',
        verbose_name=_('Vendeur'),
    )
    title       = models.CharField(max_length=180, verbose_name=_('Titre'))
    description = models.TextField(verbose_name=_('Description'))
    category    = models.CharField(
        max_length=30, choices=CATEGORY_CHOICES,
        default='autres', verbose_name=_('Catégorie'),
    )
    condition   = models.CharField(
        max_length=20, choices=CONDITION_CHOICES,
        default='bon', verbose_name=_('État'),
    )

    # ── Prix ──────────────────────────────────────────────────────────────────
    price           = models.DecimalField(
        max_digits=12, decimal_places=0,
        null=True, blank=True,
        verbose_name=_('Prix (Ar)'),
        help_text=_('Laisser vide pour "Prix à discuter"'),
    )
    price_negotiable = models.BooleanField(default=False, verbose_name=_('Prix négociable'))

    # ── Localisation ──────────────────────────────────────────────────────────
    location    = models.CharField(
        max_length=120,
        verbose_name=_('Localisation'),
        help_text=_('Ville / quartier (ex: Antananarivo, Analakely)'),
    )

    # ── Contact ───────────────────────────────────────────────────────────────
    contact_phone = models.CharField(
        max_length=20, blank=True, default='',
        verbose_name=_('Téléphone / WhatsApp'),
    )
    show_phone  = models.BooleanField(
        default=True,
        verbose_name=_('Afficher le numéro publiquement'),
    )

    # ── Meta ──────────────────────────────────────────────────────────────────
    status      = models.CharField(
        max_length=10, choices=STATUS_CHOICES,
        default='active', verbose_name=_('Statut'),
    )
    views_count = models.PositiveIntegerField(default=0, verbose_name=_('Vues'))
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Annonce')
        verbose_name_plural = _('Annonces')
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['category', '-created_at']),
            models.Index(fields=['seller', '-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'[{self.get_category_display()}] {self.title} — {self.seller}'

    def get_primary_image(self):
        """Retourne la photo principale ou None."""
        img = self.images.filter(is_primary=True).first()
        if not img:
            img = self.images.first()
        return img

    def increment_views(self):
        Annonce.objects.filter(pk=self.pk).update(views_count=models.F('views_count') + 1)

    @property
    def formatted_price(self):
        if self.price is None:
            return 'Prix à discuter'
        return f'{int(self.price):,} Ar'.replace(',', ' ')

    @property
    def is_active(self):
        return self.status == 'active'


class AnnonceImage(models.Model):
    """
    Photo attachée à une annonce du Bazar.
    Une annonce peut avoir jusqu'à 8 photos (validation dans le formulaire).
    """
    annonce    = models.ForeignKey(
        Annonce, on_delete=models.CASCADE,
        related_name='images', verbose_name=_('Annonce'),
    )
    image      = models.ImageField(
        upload_to='bazar/annonces/%Y/%m/',
        verbose_name=_('Image'),
    )
    is_primary = models.BooleanField(default=False, verbose_name=_('Photo principale'))
    order      = models.PositiveSmallIntegerField(default=0, verbose_name=_('Ordre'))

    class Meta:
        ordering = ['is_primary', 'order']
        verbose_name = _('Photo d\'annonce')
        verbose_name_plural = _('Photos d\'annonce')

    def __str__(self):
        return f'Photo {self.pk} — {self.annonce.title}'
