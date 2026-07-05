from django.db import models
from django.conf import settings
from django.utils import timezone
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
    region      = models.CharField(
        max_length=30, blank=True, default='',
        verbose_name=_('Région'),
        help_text=_('Région de Madagascar (pour le filtre "Près de chez moi")'),
        db_index=True,
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
    bumped_at   = models.DateTimeField(
        null=True, blank=True, default=None,
        verbose_name=_('Rafraîchi le'),
        help_text=_('Date du dernier bump — utilisé pour remonter en tête de liste (1 fois / 24h).'),
        db_index=True,
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Annonce')
        verbose_name_plural = _('Annonces')
        indexes = [
            models.Index(fields=['-created_at'],          name='bazar_annonce_created_idx'),
            models.Index(fields=['category', '-created_at'], name='bazar_annonce_cat_idx'),
            models.Index(fields=['seller', '-created_at'],   name='bazar_annonce_seller_idx'),
            models.Index(fields=['status'],                name='bazar_annonce_status_idx'),
        ]

    def __str__(self):
        return f'[{self.get_category_display()}] {self.title} — {self.seller}'

    def get_primary_image(self):
        """Retourne la photo principale ou None.
        Utilise self.images.all() pour profiter du prefetch_related cache
        et éviter les requêtes N+1 sur la liste des annonces."""
        all_images = list(self.images.all())   # uses prefetch cache
        if not all_images:
            return None
        primary = next((img for img in all_images if img.is_primary), None)
        return primary or all_images[0]

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
        ordering = ['-is_primary', 'order']   # is_primary=True (1) > False (0) → principale en premier
        verbose_name = _('Photo d\'annonce')
        verbose_name_plural = _('Photos d\'annonce')

    def __str__(self):
        return f'Photo {self.pk} — {self.annonce.title}'


class SellerVerification(models.Model):
    """
    Demande de vérification d'un vendeur — niveau compte (OneToOne).
    L'admin approuve ou rejette manuellement depuis l'interface d'administration.

    Avantages vendeur vérifié (status='approved') :
    - Badge ✓ sur ses annonces et son profil
    - Priorité dans les résultats de recherche (annonces boostées)
    - Filtre "Vendeurs vérifiés" dans le bazar
    - Quota photos étendu : MAX_IMAGES passe de 8 à 12
    """

    # ── Statuts possibles ──────────────────────────────────────────────────────
    STATUS_PENDING  = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_PENDING,  _('En attente')),
        (STATUS_APPROVED, _('Approuvé')),
        (STATUS_REJECTED, _('Refusé')),
    ]

    # ── Champs ─────────────────────────────────────────────────────────────────
    seller = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='seller_verification',
        verbose_name=_('Vendeur'),
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name=_('Statut'),
        db_index=True,
    )
    # Message libre du vendeur lors de sa demande
    message = models.TextField(
        blank=True, default='',
        verbose_name=_('Message du vendeur'),
        help_text=_('Pourquoi souhaitez-vous être vérifié ? (facultatif)'),
    )
    # Notes internes de l'admin (non visibles par le vendeur)
    admin_notes = models.TextField(
        blank=True, default='',
        verbose_name=_('Notes admin'),
    )
    # Timestamps
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name=_('Demande le'))
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Examinée le'))
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='verifications_reviewed',
        verbose_name=_('Examinée par'),
    )

    class Meta:
        verbose_name        = _('Vérification vendeur')
        verbose_name_plural = _('Vérifications vendeurs')
        ordering            = ['-created_at']

    def __str__(self):
        return f'{self.seller} — {self.get_status_display()}'

    # ── Propriétés utilitaires ─────────────────────────────────────────────────

    @property
    def is_approved(self):
        return self.status == self.STATUS_APPROVED

    @property
    def is_pending(self):
        return self.status == self.STATUS_PENDING

    @property
    def is_rejected(self):
        return self.status == self.STATUS_REJECTED

    # ── Helpers admin ──────────────────────────────────────────────────────────

    def approve(self, reviewed_by=None, notes=''):
        self.status      = self.STATUS_APPROVED
        self.reviewed_at = timezone.now()
        self.reviewed_by = reviewed_by
        if notes:
            self.admin_notes = notes
        self.save(update_fields=['status', 'reviewed_at', 'reviewed_by', 'admin_notes'])

    def reject(self, reviewed_by=None, notes=''):
        self.status      = self.STATUS_REJECTED
        self.reviewed_at = timezone.now()
        self.reviewed_by = reviewed_by
        if notes:
            self.admin_notes = notes
        self.save(update_fields=['status', 'reviewed_at', 'reviewed_by', 'admin_notes'])


class BazarFavori(models.Model):
    """
    Favori Bazar — un utilisateur sauvegarde une annonce pour y revenir plus tard.
    """
    user    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bazar_favoris',
        verbose_name=_('Utilisateur'),
    )
    annonce = models.ForeignKey(
        Annonce,
        on_delete=models.CASCADE,
        related_name='favoris',
        verbose_name=_('Annonce'),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Ajouté le'))

    class Meta:
        unique_together = ('user', 'annonce')
        ordering        = ['-created_at']
        verbose_name        = _('Favori Bazar')
        verbose_name_plural = _('Favoris Bazar')

    def __str__(self):
        return f'{self.user} ♥ {self.annonce.title}'
