from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


REGION_CHOICES = [
    ('analamanga',      'Analamanga'),
    ('vakinankaratra',  'Vakinankaratra'),
    ('itasy',           'Itasy'),
    ('bongolava',       'Bongolava'),
    ('haute_matsiatra', 'Haute Matsiatra'),
    ('amoron_maniana',  "Amoron'i Mania"),
    ('vatovavy',        'Vatovavy'),
    ('fitovinany',      'Fitovinany'),
    ('atsimo_atsinanana','Atsimo-Atsinanana'),
    ('atsinanana',      'Atsinanana'),
    ('analanjirofo',    'Analanjirofo'),
    ('alaotra_mangoro', 'Alaotra Mangoro'),
    ('boeny',           'Boeny'),
    ('sofia',           'Sofia'),
    ('betsiboka',       'Betsiboka'),
    ('melaky',          'Melaky'),
    ('atsimo_andrefana','Atsimo-Andrefana'),
    ('androy',          'Androy'),
    ('anosy',           'Anosy'),
    ('menabe',          'Menabe'),
    ('diana',           'Diana'),
    ('sava',            'SAVA'),
]

LIEU_CATEGORY_CHOICES = [
    ('nature',     _('Nature & Paysages')),
    ('plage',      _('Plages & Côtes')),
    ('histoire',   _('Histoire & Culture')),
    ('faune',      _('Faune & Parcs naturels')),
    ('montagne',   _('Montagnes & Randonnées')),
    ('circuit',    _('Circuits & Routes')),
    ('ville',      _('Villes & Villages')),
    ('aventure',   _('Aventure & Sport')),
]

TRANSPORT_CHOICES = [
    ('voiture',    _('Voiture')),
    ('moto',       _('Moto')),
    ('4x4',        _('4×4 / Tout-terrain')),
    ('bateau',     _('Bateau / Pirogue')),
    ('velo',       _('Vélo')),
    ('pieds',      _('À pied')),
    ('taxi_brousse',_('Taxi-brousse')),
    ('avion',      _('Avion')),
]


class LieuTouristique(models.Model):
    name        = models.CharField(max_length=200, verbose_name=_('Nom du lieu'))
    slug        = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(verbose_name=_('Description'))
    category    = models.CharField(max_length=20, choices=LIEU_CATEGORY_CHOICES,
                                   default='nature', verbose_name=_('Catégorie'))
    region      = models.CharField(max_length=30, choices=REGION_CHOICES,
                                   blank=True, default='', verbose_name=_('Région'), db_index=True)
    address     = models.CharField(max_length=250, blank=True, default='',
                                   verbose_name=_('Adresse / GPS'))
    best_period = models.CharField(max_length=120, blank=True, default='',
                                   verbose_name=_('Meilleure période pour visiter'))
    entry_fee   = models.CharField(max_length=80, blank=True, default='',
                                   verbose_name=_('Entrée / Tarif'))
    tips        = models.TextField(blank=True, default='', verbose_name=_('Conseils pratiques'))
    added_by    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='lieux_ajoutes')
    is_approved = models.BooleanField(default=False, verbose_name=_('Approuvé'), db_index=True)
    views_count = models.PositiveIntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Lieu touristique')
        verbose_name_plural = _('Lieux touristiques')

    def __str__(self):
        return self.name

    def get_primary_image(self):
        return self.images.filter(is_primary=True).first() or self.images.first()

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base = slugify(self.name)
            slug = base
            n = 1
            while LieuTouristique.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'; n += 1
            self.slug = slug
        super().save(*args, **kwargs)


class LieuImage(models.Model):
    lieu       = models.ForeignKey(LieuTouristique, on_delete=models.CASCADE,
                                   related_name='images')
    image      = models.ImageField(upload_to='tourisme/lieux/%Y/%m/')
    caption    = models.CharField(max_length=200, blank=True, default='')
    is_primary = models.BooleanField(default=False)
    order      = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['-is_primary', 'order']


class GuideTouristique(models.Model):
    user        = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                        related_name='guide_profile',
                                        verbose_name=_('Utilisateur'))
    bio         = models.TextField(verbose_name=_('Présentation / Bio'))
    languages   = models.CharField(max_length=250, blank=True, default='',
                                   verbose_name=_('Langues parlées'),
                                   help_text=_('Ex: Malagasy, Français, Anglais'))
    regions_covered = models.TextField(blank=True, default='',
                                       verbose_name=_('Régions couvertes'))
    transport_modes = models.CharField(max_length=250, blank=True, default='',
                                       verbose_name=_('Moyens de déplacement'),
                                       help_text=_('Ex: Voiture, 4×4, Pirogue'))
    specialities = models.CharField(max_length=250, blank=True, default='',
                                    verbose_name=_('Spécialités / Types de circuit'),
                                    help_text=_('Ex: Faune, Randonnée, Culturel'))
    conditions  = models.TextField(blank=True, default='',
                                   verbose_name=_('Conditions & Tarifs'),
                                   help_text=_('Prix journalier, inclusions, exclusions…'))
    prix_jour   = models.DecimalField(max_digits=10, decimal_places=0,
                                      null=True, blank=True,
                                      verbose_name=_('Prix indicatif / jour (Ar)'))
    phone       = models.CharField(max_length=30, blank=True, default='',
                                   verbose_name=_('Téléphone / WhatsApp'))
    years_experience = models.PositiveSmallIntegerField(default=0,
                                                         verbose_name=_('Années d\'expérience'))
    max_group_size   = models.PositiveSmallIntegerField(default=10,
                                                         verbose_name=_('Taille max du groupe'))
    photo       = models.ImageField(upload_to='tourisme/guides/%Y/%m/',
                                    null=True, blank=True, verbose_name=_('Photo'))
    is_verified = models.BooleanField(default=False, verbose_name=_('Guide vérifié'), db_index=True)
    is_active   = models.BooleanField(default=True, verbose_name=_('Disponible'), db_index=True)
    lieux_favoris = models.ManyToManyField(LieuTouristique, blank=True,
                                            related_name='guides',
                                            verbose_name=_('Lieux couverts'))
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_verified', '-created_at']
        verbose_name = _('Guide touristique')
        verbose_name_plural = _('Guides touristiques')

    def __str__(self):
        # Account étend AbstractBaseUser (pas AbstractUser) → pas de get_full_name()
        return f'Guide: {self.user.username}'

    @property
    def display_name(self):
        # Account n'a pas first_name/last_name — on utilise uniquement username
        return self.user.username

    @property
    def transport_list(self):
        return [t.strip() for t in self.transport_modes.split(',') if t.strip()]

    @property
    def language_list(self):
        return [l.strip() for l in self.languages.split(',') if l.strip()]
