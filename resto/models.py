"""
resto/models.py — Section « Resto » de Vazimba : commande de repas et livraison,
sur le modèle d'Uber Eats.

Vue d'ensemble :
    Restaurant ─┬─ MenuCategory ─ MenuItem ─ OptionGroup ─ Option
                ├─ Courier (livreurs rattachés, facultatif)
                └─ Order ─┬─ OrderItem ─ OrderItemOption   (photo figée du panier)
                          └─ OrderEvent                    (historique des statuts)
    Cart ─ CartItem ─ (options)                            (panier serveur, 1 resto à la fois)

Toutes les sommes sont en ariary, sans décimales (comme dans le Bazar).
"""
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from regions import REGION_CHOICES


def _fmt_ar(value):
    """12500 → '12 500 Ar' (même rendu que Annonce.formatted_price)."""
    if value is None:
        return ''
    return f'{int(value):,} Ar'.replace(',', ' ')


# ═══════════════════════════════════════════════════════════════════════════════
# Vendeur / restaurant
# ═══════════════════════════════════════════════════════════════════════════════

class Restaurant(models.Model):
    """
    Un vendeur de repas : restaurant, gargote, pâtisserie, traiteur…
    Un compte peut posséder plusieurs restaurants (chaîne, plusieurs points de vente).
    """

    CATEGORY_CHOICES = [
        ('restaurant', _('Restaurant')),
        ('fast_food',  _('Fast-food & Snack')),
        ('gargote',    _('Gargote & Hotely')),
        ('patisserie', _('Pâtisserie & Boulangerie')),
        ('boissons',   _('Boissons & Jus')),
        ('traiteur',   _('Traiteur & Plats maison')),
        ('epicerie',   _('Épicerie & Courses')),
        ('autre',      _('Autre')),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='restaurants', verbose_name=_('Propriétaire'),
    )
    name        = models.CharField(max_length=120, verbose_name=_('Nom'))
    slug        = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True, default='', verbose_name=_('Description'))
    category    = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default='restaurant',
        verbose_name=_('Catégorie'), db_index=True,
    )
    logo   = models.ImageField(upload_to='resto/logos/%Y/%m/', null=True, blank=True, verbose_name=_('Logo'))
    banner = models.ImageField(upload_to='resto/banners/%Y/%m/', null=True, blank=True, verbose_name=_('Bannière'))

    # ── Contact & localisation ────────────────────────────────────────────────
    phone   = models.CharField(max_length=30, blank=True, default='', verbose_name=_('Téléphone / WhatsApp'))
    address = models.CharField(
        max_length=250, verbose_name=_('Adresse'),
        help_text=_('Quartier, rue, repère (ex: Analakely, en face de la pharmacie)'),
    )
    region = models.CharField(
        max_length=30, choices=REGION_CHOICES, blank=True, default='',
        verbose_name=_('Région'), db_index=True,
    )
    latitude  = models.FloatField(null=True, blank=True, verbose_name=_('Latitude'))
    longitude = models.FloatField(null=True, blank=True, verbose_name=_('Longitude'))

    # ── Fonctionnement ────────────────────────────────────────────────────────
    opening_hours = models.CharField(
        max_length=250, blank=True, default='',
        verbose_name=_('Horaires'), help_text=_('Ex : Lun–Sam 10h–22h'),
    )
    is_open = models.BooleanField(
        default=True, verbose_name=_('Ouvert (accepte les commandes)'), db_index=True,
        help_text=_('Décochez pour suspendre temporairement les commandes.'),
    )
    offers_delivery = models.BooleanField(default=True, verbose_name=_('Propose la livraison'))
    offers_pickup   = models.BooleanField(default=True, verbose_name=_('Propose le retrait sur place'))
    delivery_fee = models.DecimalField(
        max_digits=12, decimal_places=0, default=0, verbose_name=_('Frais de livraison (Ar)'),
    )
    min_order = models.DecimalField(
        max_digits=12, decimal_places=0, default=0, verbose_name=_('Commande minimum (Ar)'),
    )
    avg_prep_minutes = models.PositiveSmallIntegerField(
        default=30, verbose_name=_('Temps de préparation moyen (min)'),
    )

    # ── Modération ────────────────────────────────────────────────────────────
    is_approved = models.BooleanField(default=False, verbose_name=_('Approuvé par Vazimba'), db_index=True)
    is_active   = models.BooleanField(default=True, verbose_name=_('Actif'), db_index=True)

    views_count = models.PositiveIntegerField(default=0, verbose_name=_('Vues'))
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Restaurant')
        verbose_name_plural = _('Restaurants')
        indexes = [
            models.Index(fields=['region', 'is_approved', 'is_active'], name='resto_restaurant_region_idx'),
            models.Index(fields=['category', '-created_at'],           name='resto_restaurant_cat_idx'),
        ]

    def __str__(self):
        return self.name

    @property
    def get_cname(self):
        # Utilisé par notification.utils.LazyNotificationEncoder pour typer la notification
        return 'Restaurant'

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or 'resto'
            slug, n = base, 1
            while Restaurant.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    # ── Helpers ───────────────────────────────────────────────────────────────
    @property
    def is_visible(self):
        return self.is_approved and self.is_active

    @property
    def can_order(self):
        return self.is_visible and self.is_open

    @property
    def has_position(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def formatted_delivery_fee(self):
        return _('Livraison gratuite') if not self.delivery_fee else _fmt_ar(self.delivery_fee)

    def increment_views(self):
        Restaurant.objects.filter(pk=self.pk).update(views_count=models.F('views_count') + 1)


# ═══════════════════════════════════════════════════════════════════════════════
# Menu
# ═══════════════════════════════════════════════════════════════════════════════

class MenuCategory(models.Model):
    """Rubrique du menu : « Entrées », « Plats », « Boissons »…"""
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE,
                                   related_name='menu_categories', verbose_name=_('Restaurant'))
    name  = models.CharField(max_length=80, verbose_name=_('Nom de la rubrique'))
    order = models.PositiveSmallIntegerField(default=0, verbose_name=_('Ordre'))

    class Meta:
        ordering = ['order', 'id']
        verbose_name = _('Rubrique de menu')
        verbose_name_plural = _('Rubriques de menu')

    def __str__(self):
        return f'{self.restaurant.name} › {self.name}'


class MenuItem(models.Model):
    """Un plat, une boisson, un article du menu."""
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE,
                                   related_name='items', verbose_name=_('Restaurant'))
    category = models.ForeignKey(
        MenuCategory, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='items', verbose_name=_('Rubrique'),
    )
    name        = models.CharField(max_length=120, verbose_name=_('Nom du plat'))
    description = models.TextField(blank=True, default='', verbose_name=_('Description'),
                                   help_text=_('Ingrédients, portion, accompagnement…'))
    price = models.DecimalField(max_digits=12, decimal_places=0, verbose_name=_('Prix (Ar)'))
    image = models.ImageField(upload_to='resto/items/%Y/%m/', null=True, blank=True, verbose_name=_('Photo'))
    # Ingrédients, un par ligne. Le client peut en décocher (« sans oignons ») ;
    # un « ! » devant un ingrédient le rend obligatoire (non retirable) : « !Riz ».
    ingredients = models.TextField(
        blank=True, default='', verbose_name=_('Ingrédients'),
        help_text=_("Un par ligne. Le client pourra les décocher. Mettez « ! » devant ceux qu'on ne peut pas retirer (ex : !Riz)."),
    )
    # Comment le plat est préparé (cuisson, mode de préparation, temps…) — affiché au client
    preparation = models.TextField(
        blank=True, default='', verbose_name=_('Préparation'),
        help_text=_('Comment le plat est préparé : cuisson, mode de préparation, temps, particularités.'),
    )
    is_available = models.BooleanField(default=True, verbose_name=_('Disponible'), db_index=True)
    order = models.PositiveSmallIntegerField(default=0, verbose_name=_('Ordre'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category__order', 'order', 'id']
        verbose_name = _('Plat')
        verbose_name_plural = _('Plats')

    def __str__(self):
        return f'{self.name} — {_fmt_ar(self.price)}'

    @property
    def formatted_price(self):
        return _fmt_ar(self.price)

    @property
    def ingredient_list(self):
        """
        Un ingrédient par ligne, format « Nom|prix|inclus|choix » :
            prix   : supplément en Ar (0 = compris dans le prix du plat)
            inclus : 1 = coché par défaut, 0 = décoché par défaut
            choix  : 1 = le client choisit (Avec / Sans), 0 = toujours inclus
        Compatibilité : « Nom » seul = 0|1|1 ; « !Nom » = 0|1|0 (toujours inclus).
        → [{'name', 'price', 'default_on', 'locked', 'removable'}, …]
        """
        out = []
        for raw in self.ingredients.splitlines():
            raw = raw.strip()
            if not raw:
                continue
            parts = [p.strip() for p in raw.split('|')]
            name = parts[0]
            locked_legacy = name.startswith('!')
            name = name.lstrip('!').strip()
            if not name:
                continue
            try:
                price = max(0, int(parts[1])) if len(parts) > 1 and parts[1] else 0
            except ValueError:
                price = 0
            default_on = (parts[2] != '0') if len(parts) > 2 and parts[2] != '' else True
            choice = (parts[3] != '0') if len(parts) > 3 and parts[3] != '' else not locked_legacy
            out.append({'name': name, 'price': price, 'default_on': default_on or not choice,
                        'locked': not choice, 'removable': choice})
        return out

    @property
    def ingredient_names(self):
        return ', '.join(i['name'] for i in self.ingredient_list)

    @property
    def is_composable(self):
        """Vrai si au moins un ingrédient est payant ou décoché par défaut : le client compose son plat."""
        return any(i['price'] or not i['default_on'] for i in self.ingredient_list)


class OptionGroup(models.Model):
    """
    Groupe de choix rattaché à un plat, à la manière d'Uber Eats :
    « Choisissez votre sauce » (obligatoire, 1 choix), « Suppléments » (0 à 5 choix)…
    """
    item = models.ForeignKey(MenuItem, on_delete=models.CASCADE,
                             related_name='option_groups', verbose_name=_('Plat'))
    name = models.CharField(max_length=100, verbose_name=_('Titre du groupe'),
                            help_text=_('Ex : Sauce, Cuisson, Suppléments, Boisson'))
    min_select = models.PositiveSmallIntegerField(
        default=0, verbose_name=_('Choix minimum'),
        help_text=_('0 = facultatif, 1 = au moins un choix obligatoire'),
    )
    max_select = models.PositiveSmallIntegerField(
        default=1, verbose_name=_('Choix maximum'),
        help_text=_('1 = un seul choix (boutons ronds), >1 = plusieurs cases à cocher, 0 = illimité'),
    )
    order = models.PositiveSmallIntegerField(default=0, verbose_name=_('Ordre'))

    class Meta:
        ordering = ['order', 'id']
        verbose_name = _('Groupe d\'options')
        verbose_name_plural = _('Groupes d\'options')

    def __str__(self):
        return f'{self.item.name} › {self.name}'

    @property
    def is_required(self):
        return self.min_select > 0

    @property
    def is_single(self):
        return self.max_select == 1


class Option(models.Model):
    """Un choix dans un groupe : « Sauce piment », « Fromage en plus (+1 000 Ar) »…"""
    group = models.ForeignKey(OptionGroup, on_delete=models.CASCADE,
                              related_name='options', verbose_name=_('Groupe'))
    name = models.CharField(max_length=100, verbose_name=_('Nom'))
    extra_price = models.DecimalField(
        max_digits=12, decimal_places=0, default=0, verbose_name=_('Supplément (Ar)'),
    )
    is_available = models.BooleanField(default=True, verbose_name=_('Disponible'))
    order = models.PositiveSmallIntegerField(default=0, verbose_name=_('Ordre'))

    class Meta:
        ordering = ['order', 'id']
        verbose_name = _('Option')
        verbose_name_plural = _('Options')

    def __str__(self):
        extra = f' (+{_fmt_ar(self.extra_price)})' if self.extra_price else ''
        return f'{self.name}{extra}'

    @property
    def formatted_extra(self):
        return f'+{_fmt_ar(self.extra_price)}' if self.extra_price else ''


# ═══════════════════════════════════════════════════════════════════════════════
# Livreurs
# ═══════════════════════════════════════════════════════════════════════════════

class Courier(models.Model):
    """
    Profil livreur. Un livreur peut être rattaché à un restaurant (ses propres
    livreurs) ou indépendant (restaurant vide) : il voit alors les commandes
    « prêtes » de sa région et peut les prendre.
    """
    VEHICLE_CHOICES = [
        ('moto',    _('Moto / Scooter')),
        ('velo',    _('Vélo')),
        ('voiture', _('Voiture')),
        ('pied',    _('À pied')),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='courier_profile', verbose_name=_('Utilisateur'))
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='couriers', verbose_name=_('Restaurant de rattachement'),
        help_text=_('Vide = livreur indépendant'),
    )
    phone   = models.CharField(max_length=30, verbose_name=_('Téléphone'))
    vehicle = models.CharField(max_length=10, choices=VEHICLE_CHOICES, default='moto', verbose_name=_('Véhicule'))
    region  = models.CharField(max_length=30, choices=REGION_CHOICES, blank=True, default='',
                               verbose_name=_('Région'), db_index=True)
    is_available = models.BooleanField(default=False, verbose_name=_('Disponible'), db_index=True)
    is_approved  = models.BooleanField(default=False, verbose_name=_('Approuvé'), db_index=True)

    # ── Identité (confiance) ──────────────────────────────────────────────────
    full_name = models.CharField(max_length=120, blank=True, default='', verbose_name=_('Nom complet (comme sur la CIN)'))
    photo = models.ImageField(upload_to='resto/couriers/%Y/%m/', null=True, blank=True, verbose_name=_('Photo (visage bien visible)'))
    bio = models.TextField(blank=True, default='', verbose_name=_('Présentation'),
                           help_text=_('Quelques mots sur vous : expérience, ponctualité, ce que les clients peuvent attendre.'))
    # CIN malgache : 12 chiffres. Numéro et scans visibles uniquement par l'équipe Vazimba (admin).
    cin_number = models.CharField(max_length=20, blank=True, default='', verbose_name=_('N° de CIN (12 chiffres)'))
    cin_front = models.ImageField(upload_to='resto/cin/%Y/%m/', null=True, blank=True, verbose_name=_('CIN recto'))
    cin_back  = models.ImageField(upload_to='resto/cin/%Y/%m/', null=True, blank=True, verbose_name=_('CIN verso'))
    cin_verified = models.BooleanField(default=False, verbose_name=_('Identité vérifiée par Vazimba'), db_index=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='couriers_verified')
    admin_notes = models.TextField(blank=True, default='', verbose_name=_('Notes admin'))

    # ── Véhicule ──────────────────────────────────────────────────────────────
    vehicle_plate = models.CharField(max_length=20, blank=True, default='', verbose_name=_('Immatriculation'))
    vehicle_photo = models.ImageField(upload_to='resto/vehicles/%Y/%m/', null=True, blank=True, verbose_name=_('Photo du véhicule'))

    # ── Zone & disponibilités ─────────────────────────────────────────────────
    zones = models.CharField(max_length=250, blank=True, default='', verbose_name=_('Quartiers couverts'),
                             help_text=_('Ex : Analakely, Isoraka, Ankorondrano, 67 Ha'))
    hours = models.CharField(max_length=120, blank=True, default='', verbose_name=_('Disponibilités'),
                             help_text=_('Ex : Lun–Sam 10h–22h'))
    languages = models.CharField(max_length=120, blank=True, default='Malagasy, Français', verbose_name=_('Langues parlées'))
    years_experience = models.PositiveSmallIntegerField(default=0, verbose_name=_('Années d\'expérience en livraison'))

    # ── Paiement des frais de livraison ───────────────────────────────────────
    MM_CHOICES = [
        ('',       _('Espèces uniquement')),
        ('mvola',  'MVola'),
        ('orange', 'Orange Money'),
        ('airtel', 'Airtel Money'),
    ]
    mm_provider = models.CharField(max_length=10, choices=MM_CHOICES, blank=True, default='', verbose_name=_('Mobile money'))
    mm_number   = models.CharField(max_length=30, blank=True, default='', verbose_name=_('Numéro mobile money'))

    # ── Garant (personne de confiance joignable) ──────────────────────────────
    guarantor_name  = models.CharField(max_length=120, blank=True, default='', verbose_name=_('Nom du garant'),
                                       help_text=_('Une personne de confiance (famille, employeur, fokontany) qui répond de vous.'))
    guarantor_phone = models.CharField(max_length=30, blank=True, default='', verbose_name=_('Téléphone du garant'))

    # Dernière position connue (mise à jour par le navigateur du livreur)
    latitude  = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    position_updated_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Livreur')
        verbose_name_plural = _('Livreurs')

    def __str__(self):
        return f'Livreur: {self.user.username}'

    @property
    def display_name(self):
        return self.full_name or self.user.username

    # ── Confiance ─────────────────────────────────────────────────────────────
    @property
    def phone_verified(self):
        return bool(getattr(self.user, 'phone_verified', False))

    @property
    def profile_completion(self):
        """Pourcentage de champs de confiance renseignés (guide le livreur)."""
        checks = [self.full_name, self.photo, self.phone, self.cin_number, self.cin_front, self.cin_back,
                  self.vehicle_plate or self.vehicle == 'pied', self.zones, self.hours, self.guarantor_name,
                  self.guarantor_phone, self.bio]
        return int(100 * sum(1 for c in checks if c) / len(checks))

    @property
    def deliveries_count(self):
        return self.orders.filter(status=Order.STATUS_DELIVERED).count()

    def trust_level(self):
        """('new' | 'verified' | 'confirmed', libellé). Confirmé = vérifié + 20 livraisons + note ≥ 4.5."""
        if self.cin_verified:
            stats = OrderReview.for_courier(self)
            if self.deliveries_count >= 20 and stats['avg'] >= 4.5 and stats['payment_issues'] == 0:
                return 'confirmed', _('Livreur confirmé')
            return 'verified', _('Identité vérifiée')
        return 'new', _('Nouveau livreur')

    @property
    def zone_list(self):
        return [z.strip() for z in self.zones.split(',') if z.strip()]

    @property
    def has_position(self):
        return self.latitude is not None and self.longitude is not None

    def update_position(self, lat, lng):
        self.latitude, self.longitude = lat, lng
        self.position_updated_at = timezone.now()
        self.save(update_fields=['latitude', 'longitude', 'position_updated_at'])


# ═══════════════════════════════════════════════════════════════════════════════
# Panier (côté serveur, un restaurant à la fois — comme Uber Eats)
# ═══════════════════════════════════════════════════════════════════════════════

class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='resto_cart', verbose_name=_('Utilisateur'))
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE,
                                   related_name='carts', verbose_name=_('Restaurant'))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Panier')
        verbose_name_plural = _('Paniers')

    def __str__(self):
        return f'Panier {self.user.username} @ {self.restaurant.name}'

    @property
    def subtotal(self):
        return sum((line.line_total for line in self.lines.all()), 0)

    @property
    def total_quantity(self):
        return sum((line.quantity for line in self.lines.all()), 0)

    @property
    def delivery_fee(self):
        return self.restaurant.delivery_fee

    @property
    def total(self):
        return self.subtotal + self.delivery_fee


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='lines')
    item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name='cart_lines')
    options = models.ManyToManyField(Option, blank=True, related_name='cart_lines')
    quantity = models.PositiveSmallIntegerField(default=1)
    # Ingrédients décochés / choisis par le client, séparés par « | » (ex : « Oignons|Piment »)
    removed_ingredients  = models.CharField(max_length=300, blank=True, default='')
    included_ingredients = models.CharField(max_length=300, blank=True, default='')
    ingredients_extra = models.DecimalField(max_digits=12, decimal_places=0, default=0)   # somme des ingrédients payants choisis
    note = models.CharField(max_length=200, blank=True, default='',
                            verbose_name=_('Instructions'), help_text=_('Ex : sans oignons, bien cuit'))
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['added_at']

    def __str__(self):
        return f'{self.quantity} × {self.item.name}'

    @property
    def unit_price(self):
        return self.item.price + sum((o.extra_price for o in self.options.all()), 0) + self.ingredients_extra

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    @property
    def options_label(self):
        return ', '.join(o.name for o in self.options.all())

    @property
    def removed_list(self):
        return [x for x in self.removed_ingredients.split('|') if x]

    @property
    def removed_label(self):
        return ', '.join(self.removed_list)

    @property
    def included_label(self):
        return ', '.join(x for x in self.included_ingredients.split('|') if x)


# ═══════════════════════════════════════════════════════════════════════════════
# Commandes
# ═══════════════════════════════════════════════════════════════════════════════

class Order(models.Model):
    """
    Une commande passée à un restaurant. Les lignes (OrderItem) figent nom, prix
    et options au moment de la commande : modifier le menu ensuite ne change rien.
    """

    # ── Cycle de vie ──────────────────────────────────────────────────────────
    STATUS_PENDING    = 'pending'      # envoyée, en attente du restaurant
    STATUS_ACCEPTED   = 'accepted'     # acceptée par le restaurant
    STATUS_PREPARING  = 'preparing'    # en cuisine
    STATUS_READY      = 'ready'        # prête (à récupérer par le livreur ou le client)
    STATUS_PICKED_UP  = 'picked_up'    # récupérée par le livreur
    STATUS_DELIVERING = 'delivering'   # en route
    STATUS_DELIVERED  = 'delivered'    # livrée / remise au client
    STATUS_CANCELLED  = 'cancelled'    # annulée par le client
    STATUS_REFUSED    = 'refused'      # refusée par le restaurant

    STATUS_CHOICES = [
        (STATUS_PENDING,    _('En attente du restaurant')),
        (STATUS_ACCEPTED,   _('Acceptée')),
        (STATUS_PREPARING,  _('En préparation')),
        (STATUS_READY,      _('Prête')),
        (STATUS_PICKED_UP,  _('Récupérée par le livreur')),
        (STATUS_DELIVERING, _('En cours de livraison')),
        (STATUS_DELIVERED,  _('Livrée')),
        (STATUS_CANCELLED,  _('Annulée')),
        (STATUS_REFUSED,    _('Refusée')),
    ]
    # Ordre logique pour la barre de progression (les statuts finaux négatifs à part)
    STATUS_FLOW = [STATUS_PENDING, STATUS_ACCEPTED, STATUS_PREPARING, STATUS_READY,
                   STATUS_PICKED_UP, STATUS_DELIVERING, STATUS_DELIVERED]
    FINAL_STATUSES = {STATUS_DELIVERED, STATUS_CANCELLED, STATUS_REFUSED}

    MODE_DELIVERY = 'delivery'
    MODE_PICKUP   = 'pickup'
    MODE_CHOICES = [
        (MODE_DELIVERY, _('Livraison')),
        (MODE_PICKUP,   _('Retrait sur place')),
    ]

    PAYMENT_CHOICES = [
        ('cash',   _('Espèces à la livraison')),
        ('mvola',  _('MVola')),
        ('orange', _('Orange Money')),
        ('airtel', _('Airtel Money')),
    ]

    number = models.CharField(max_length=12, unique=True, editable=False, verbose_name=_('N° de commande'))
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name='resto_orders', verbose_name=_('Client'))
    restaurant = models.ForeignKey(Restaurant, on_delete=models.PROTECT,
                                   related_name='orders', verbose_name=_('Restaurant'))
    courier = models.ForeignKey(Courier, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='orders', verbose_name=_('Livreur'))

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING,
                              verbose_name=_('Statut'), db_index=True)
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default=MODE_DELIVERY, verbose_name=_('Mode'))
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='cash',
                                      verbose_name=_('Paiement'))

    # ── Client & livraison ────────────────────────────────────────────────────
    customer_name  = models.CharField(max_length=80, verbose_name=_('Nom du client'))
    customer_phone = models.CharField(max_length=30, verbose_name=_('Téléphone du client'))
    delivery_address = models.CharField(max_length=250, blank=True, default='', verbose_name=_('Adresse de livraison'))
    delivery_latitude  = models.FloatField(null=True, blank=True)
    delivery_longitude = models.FloatField(null=True, blank=True)
    note = models.TextField(blank=True, default='', verbose_name=_('Message au restaurant'))

    # Point de retrait figé (au cas où le restaurant déménage ou change sa position)
    pickup_address   = models.CharField(max_length=250, blank=True, default='')
    pickup_latitude  = models.FloatField(null=True, blank=True)
    pickup_longitude = models.FloatField(null=True, blank=True)

    # ── Montants (figés) ──────────────────────────────────────────────────────
    subtotal     = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    delivery_fee = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    total        = models.DecimalField(max_digits=12, decimal_places=0, default=0)

    # ── Horodatage du parcours ────────────────────────────────────────────────
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)
    accepted_at  = models.DateTimeField(null=True, blank=True)
    ready_at     = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    closed_at    = models.DateTimeField(null=True, blank=True)   # annulée / refusée / livrée
    estimated_minutes = models.PositiveSmallIntegerField(null=True, blank=True,
                                                         verbose_name=_('Délai annoncé (min)'))
    refusal_reason = models.CharField(max_length=200, blank=True, default='', verbose_name=_('Motif'))

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Commande')
        verbose_name_plural = _('Commandes')
        indexes = [
            models.Index(fields=['restaurant', 'status', '-created_at'], name='resto_order_resto_status_idx'),
            models.Index(fields=['customer', '-created_at'],             name='resto_order_customer_idx'),
            models.Index(fields=['courier', 'status'],                   name='resto_order_courier_idx'),
        ]

    def __str__(self):
        return f'Commande {self.number} — {self.restaurant.name} — {self.get_status_display()}'

    @property
    def get_cname(self):
        # Utilisé par notification.utils.LazyNotificationEncoder pour typer la notification
        return 'Order'

    def save(self, *args, **kwargs):
        if not self.number:
            # Ex : VZ-7K3Q9X — court, lisible au téléphone, unique
            while True:
                candidate = 'VZ-' + secrets.token_hex(3).upper()
                if not Order.objects.filter(number=candidate).exists():
                    self.number = candidate
                    break
        super().save(*args, **kwargs)

    # ── Helpers d'état ────────────────────────────────────────────────────────
    @property
    def is_delivery(self):
        return self.mode == self.MODE_DELIVERY

    @property
    def is_final(self):
        return self.status in self.FINAL_STATUSES

    @property
    def is_cancelled(self):
        return self.status in (self.STATUS_CANCELLED, self.STATUS_REFUSED)

    @property
    def can_customer_cancel(self):
        return self.status in (self.STATUS_PENDING, self.STATUS_ACCEPTED)

    @property
    def progress_index(self):
        """Position dans STATUS_FLOW (0..6) pour la barre de progression, -1 si annulée."""
        try:
            return self.STATUS_FLOW.index(self.status)
        except ValueError:
            return -1

    @property
    def progress_steps(self):
        """Étapes affichées au client, adaptées au mode (retrait = pas de livreur)."""
        if self.is_delivery:
            flow = self.STATUS_FLOW
        else:
            flow = [self.STATUS_PENDING, self.STATUS_ACCEPTED, self.STATUS_PREPARING,
                    self.STATUS_READY, self.STATUS_DELIVERED]
        labels = dict(self.STATUS_CHOICES)
        current = flow.index(self.status) if self.status in flow else -1
        return [{'code': s, 'label': str(labels[s]), 'done': i <= current, 'current': i == current}
                for i, s in enumerate(flow)]

    @property
    def formatted_total(self):
        return _fmt_ar(self.total)

    @property
    def formatted_subtotal(self):
        return _fmt_ar(self.subtotal)

    @property
    def formatted_delivery_fee(self):
        return _('Gratuite') if not self.delivery_fee else _fmt_ar(self.delivery_fee)

    def allowed_transitions(self, actor):
        """
        Statuts vers lesquels `actor` peut faire passer la commande.
        actor ∈ {'restaurant', 'courier', 'customer'}.
        """
        s = self.status
        if actor == 'restaurant':
            table = {
                self.STATUS_PENDING:   [self.STATUS_ACCEPTED, self.STATUS_REFUSED],
                self.STATUS_ACCEPTED:  [self.STATUS_PREPARING, self.STATUS_REFUSED],
                self.STATUS_PREPARING: [self.STATUS_READY],
                # Retrait sur place : le restaurant remet la commande lui-même
                self.STATUS_READY:     [self.STATUS_DELIVERED] if not self.is_delivery else [],
            }
        elif actor == 'courier':
            table = {
                self.STATUS_READY:      [self.STATUS_PICKED_UP],
                self.STATUS_PICKED_UP:  [self.STATUS_DELIVERING],
                self.STATUS_DELIVERING: [self.STATUS_DELIVERED],
            }
        else:  # customer
            table = {
                self.STATUS_PENDING:  [self.STATUS_CANCELLED],
                self.STATUS_ACCEPTED: [self.STATUS_CANCELLED],
            }
        return table.get(s, [])

    def set_status(self, new_status, by=None, note=''):
        """Change le statut, horodate, journalise. Ne vérifie PAS les droits (voir vues)."""
        now = timezone.now()
        self.status = new_status
        if new_status == self.STATUS_ACCEPTED:
            self.accepted_at = now
        elif new_status == self.STATUS_READY:
            self.ready_at = now
        elif new_status == self.STATUS_PICKED_UP:
            self.picked_up_at = now
        elif new_status == self.STATUS_DELIVERED:
            self.delivered_at = now
            self.closed_at = now
        elif new_status in (self.STATUS_CANCELLED, self.STATUS_REFUSED):
            self.closed_at = now
            if note:
                self.refusal_reason = note[:200]
        self.save()
        OrderEvent.objects.create(order=self, status=new_status, by=by, note=note[:200])


class OrderItem(models.Model):
    """Ligne de commande : photo figée d'un plat et de ses options au moment de l'achat."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(MenuItem, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='order_lines')
    name = models.CharField(max_length=120)
    unit_price = models.DecimalField(max_digits=12, decimal_places=0)   # plat + options
    quantity = models.PositiveSmallIntegerField(default=1)
    line_total = models.DecimalField(max_digits=12, decimal_places=0)
    removed_ingredients  = models.CharField(max_length=300, blank=True, default='')   # « Oignons|Piment »
    included_ingredients = models.CharField(max_length=300, blank=True, default='')   # ingrédients choisis (plat composé)
    note = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.quantity} × {self.name}'

    @property
    def formatted_line_total(self):
        return _fmt_ar(self.line_total)

    @property
    def options_label(self):
        return ', '.join(o.name for o in self.options.all())

    @property
    def removed_label(self):
        return ', '.join(x for x in self.removed_ingredients.split('|') if x)

    @property
    def included_label(self):
        return ', '.join(x for x in self.included_ingredients.split('|') if x)


class OrderItemOption(models.Model):
    line = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name='options')
    group_name = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    extra_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.group_name}: {self.name}'


class OrderEvent(models.Model):
    """Historique des changements de statut, affiché dans le suivi de commande."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='events')
    status = models.CharField(max_length=12, choices=Order.STATUS_CHOICES)
    by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.CharField(max_length=200, blank=True, default='')
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['at']
        verbose_name = _('Événement de commande')
        verbose_name_plural = _('Événements de commande')

    def __str__(self):
        return f'{self.order.number} → {self.get_status_display()} ({self.at:%H:%M})'


# ═══════════════════════════════════════════════════════════════════════════════
# Avis croisés après commande (client ⇄ restaurant ⇄ livreur)
# ═══════════════════════════════════════════════════════════════════════════════

class OrderReview(models.Model):
    """
    Un avis laissé par l'un des trois acteurs d'une commande sur un autre :
    note sur 5, le paiement s'est-il bien passé, commentaire libre.
    Un seul avis par (commande, auteur, cible) ; il peut être modifié.
    """
    ROLE_CUSTOMER   = 'customer'
    ROLE_RESTAURANT = 'restaurant'
    ROLE_COURIER    = 'courier'
    ROLE_CHOICES = [
        (ROLE_CUSTOMER,   _('Client')),
        (ROLE_RESTAURANT, _('Restaurant')),
        (ROLE_COURIER,    _('Livreur')),
    ]
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]

    order  = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='reviews', verbose_name=_('Commande'))
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name='resto_reviews_given', verbose_name=_('Auteur'))
    author_role = models.CharField(max_length=12, choices=ROLE_CHOICES, verbose_name=_('Rôle de l\'auteur'))
    target_role = models.CharField(max_length=12, choices=ROLE_CHOICES, verbose_name=_('Rôle noté'), db_index=True)
    # Cible dénormalisée pour agréger vite (un seul des trois est renseigné)
    target_user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
                                          related_name='resto_reviews_received')
    target_restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, null=True, blank=True, related_name='reviews')
    target_courier    = models.ForeignKey(Courier, on_delete=models.CASCADE, null=True, blank=True, related_name='reviews')

    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES, default=5, verbose_name=_('Note (1-5)'))
    payment_ok = models.BooleanField(null=True, blank=True, verbose_name=_('Paiement sans problème'))
    payment_note = models.CharField(max_length=200, blank=True, default='', verbose_name=_('Précision sur le paiement'))
    comment = models.TextField(blank=True, default='', verbose_name=_('Commentaire'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('order', 'author_role', 'target_role')]
        ordering = ['-created_at']
        verbose_name = _('Avis')
        verbose_name_plural = _('Avis')

    def __str__(self):
        return f'{self.order.number} {self.author_role}→{self.target_role} {self.rating}★'

    @property
    def stars(self):
        return '★' * self.rating + '☆' * (5 - self.rating)

    # ── Agrégats ──────────────────────────────────────────────────────────────
    @staticmethod
    def summary(qs):
        """{'count': n, 'avg': 4.6, 'payment_issues': k} sur un queryset d'avis."""
        agg = qs.aggregate(count=models.Count('id'), avg=models.Avg('rating'),
                           issues=models.Count('id', filter=models.Q(payment_ok=False)))
        return {'count': agg['count'] or 0, 'avg': round(agg['avg'] or 0, 1), 'payment_issues': agg['issues'] or 0}

    @classmethod
    def for_restaurant(cls, restaurant):
        return cls.summary(cls.objects.filter(target_restaurant=restaurant))

    @classmethod
    def for_courier(cls, courier):
        return cls.summary(cls.objects.filter(target_courier=courier))

    @classmethod
    def for_customer(cls, user):
        return cls.summary(cls.objects.filter(target_user=user, target_role=cls.ROLE_CUSTOMER))
