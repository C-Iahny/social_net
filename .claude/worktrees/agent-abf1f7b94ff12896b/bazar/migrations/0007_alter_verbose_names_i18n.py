"""
Migration 0007 — Synchronise les verbose_name / help_text / choices avec les
gettext_lazy  _()  introduits dans models.py lors de l'internationalisation.

Aucun changement de schéma DB : uniquement la représentation interne Django
(migration state). Railway affichait le warning :
  « Your models in app(s): 'bazar' have changes not yet in a migration »
Cette migration le corrige définitivement.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils.translation import gettext_lazy as _


class Migration(migrations.Migration):

    dependencies = [
        ('bazar', '0006_bazarfavori'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ══════════════════════════════════════════════════════════════
        # Annonce — champs
        # ══════════════════════════════════════════════════════════════
        migrations.AlterField(
            model_name='annonce',
            name='seller',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='annonces',
                to=settings.AUTH_USER_MODEL,
                verbose_name=_('Vendeur'),
            ),
        ),
        migrations.AlterField(
            model_name='annonce',
            name='title',
            field=models.CharField(max_length=180, verbose_name=_('Titre')),
        ),
        migrations.AlterField(
            model_name='annonce',
            name='description',
            field=models.TextField(verbose_name=_('Description')),
        ),
        migrations.AlterField(
            model_name='annonce',
            name='category',
            field=models.CharField(
                choices=[
                    ('electronique', _('Électronique & Téléphones')),
                    ('vehicules',    _('Véhicules & Motos')),
                    ('immobilier',   _('Immobilier & Location')),
                    ('mode',         _('Mode & Vêtements')),
                    ('maison',       _('Maison & Mobilier')),
                    ('agriculture',  _('Agriculture & Élevage')),
                    ('alimentaire',  _('Alimentaire & Boissons')),
                    ('services',     _('Services & Prestations')),
                    ('emploi',       _('Emploi & Formation')),
                    ('artisanat',    _('Artisanat & Art')),
                    ('sports',       _('Sports & Loisirs')),
                    ('bebe',         _('Bébé & Enfants')),
                    ('autres',       _('Autres')),
                ],
                default='autres', max_length=30, verbose_name=_('Catégorie'),
            ),
        ),
        migrations.AlterField(
            model_name='annonce',
            name='condition',
            field=models.CharField(
                choices=[
                    ('neuf',     _('Neuf')),
                    ('tres_bon', _('Très bon état')),
                    ('bon',      _('Bon état')),
                    ('correct',  _('État correct')),
                    ('pieces',   _('Pour pièces')),
                ],
                default='bon', max_length=20, verbose_name=_('État'),
            ),
        ),
        migrations.AlterField(
            model_name='annonce',
            name='price',
            field=models.DecimalField(
                blank=True, decimal_places=0, max_digits=12, null=True,
                verbose_name=_('Prix (Ar)'),
                help_text=_('Laisser vide pour "Prix à discuter"'),
            ),
        ),
        migrations.AlterField(
            model_name='annonce',
            name='price_negotiable',
            field=models.BooleanField(default=False, verbose_name=_('Prix négociable')),
        ),
        migrations.AlterField(
            model_name='annonce',
            name='location',
            field=models.CharField(
                max_length=120,
                verbose_name=_('Localisation'),
                help_text=_('Ville / quartier (ex: Antananarivo, Analakely)'),
            ),
        ),
        migrations.AlterField(
            model_name='annonce',
            name='region',
            field=models.CharField(
                blank=True, db_index=True, default='', max_length=30,
                verbose_name=_('Région'),
                help_text=_('Région de Madagascar (pour le filtre "Près de chez moi")'),
            ),
        ),
        migrations.AlterField(
            model_name='annonce',
            name='contact_phone',
            field=models.CharField(
                blank=True, default='', max_length=20,
                verbose_name=_('Téléphone / WhatsApp'),
            ),
        ),
        migrations.AlterField(
            model_name='annonce',
            name='show_phone',
            field=models.BooleanField(default=True, verbose_name=_('Afficher le numéro publiquement')),
        ),
        migrations.AlterField(
            model_name='annonce',
            name='status',
            field=models.CharField(
                choices=[
                    ('active',  _('Active')),
                    ('vendue',  _('Vendue')),
                    ('pause',   _('En pause')),
                    ('expiree', _('Expirée')),
                ],
                default='active', max_length=10, verbose_name=_('Statut'),
            ),
        ),
        migrations.AlterField(
            model_name='annonce',
            name='views_count',
            field=models.PositiveIntegerField(default=0, verbose_name=_('Vues')),
        ),
        migrations.AlterField(
            model_name='annonce',
            name='bumped_at',
            field=models.DateTimeField(
                blank=True, db_index=True, default=None, null=True,
                verbose_name=_('Rafraîchi le'),
                help_text=_('Date du dernier bump — utilisé pour remonter en tête de liste (1 fois / 24h).'),
            ),
        ),
        # Annonce — Meta
        migrations.AlterModelOptions(
            name='annonce',
            options={
                'ordering': ['-created_at'],
                'verbose_name': _('Annonce'),
                'verbose_name_plural': _('Annonces'),
            },
        ),

        # ══════════════════════════════════════════════════════════════
        # AnnonceImage — champs
        # ══════════════════════════════════════════════════════════════
        migrations.AlterField(
            model_name='annonceimage',
            name='annonce',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='images',
                to='bazar.annonce',
                verbose_name=_('Annonce'),
            ),
        ),
        migrations.AlterField(
            model_name='annonceimage',
            name='image',
            field=models.ImageField(
                upload_to='bazar/annonces/%Y/%m/',
                verbose_name=_('Image'),
            ),
        ),
        migrations.AlterField(
            model_name='annonceimage',
            name='is_primary',
            field=models.BooleanField(default=False, verbose_name=_('Photo principale')),
        ),
        migrations.AlterField(
            model_name='annonceimage',
            name='order',
            field=models.PositiveSmallIntegerField(default=0, verbose_name=_('Ordre')),
        ),
        # AnnonceImage — Meta
        migrations.AlterModelOptions(
            name='annonceimage',
            options={
                'ordering': ['-is_primary', 'order'],
                'verbose_name': _("Photo d'annonce"),
                'verbose_name_plural': _("Photos d'annonce"),
            },
        ),

        # ══════════════════════════════════════════════════════════════
        # SellerVerification — champs
        # ══════════════════════════════════════════════════════════════
        migrations.AlterField(
            model_name='sellerverification',
            name='seller',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='seller_verification',
                to=settings.AUTH_USER_MODEL,
                verbose_name=_('Vendeur'),
            ),
        ),
        migrations.AlterField(
            model_name='sellerverification',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending',  _('En attente')),
                    ('approved', _('Approuvé')),
                    ('rejected', _('Refusé')),
                ],
                db_index=True, default='pending', max_length=10,
                verbose_name=_('Statut'),
            ),
        ),
        migrations.AlterField(
            model_name='sellerverification',
            name='message',
            field=models.TextField(
                blank=True, default='',
                verbose_name=_('Message du vendeur'),
                help_text=_('Pourquoi souhaitez-vous être vérifié ? (facultatif)'),
            ),
        ),
        migrations.AlterField(
            model_name='sellerverification',
            name='admin_notes',
            field=models.TextField(blank=True, default='', verbose_name=_('Notes admin')),
        ),
        migrations.AlterField(
            model_name='sellerverification',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, verbose_name=_('Demande le')),
        ),
        migrations.AlterField(
            model_name='sellerverification',
            name='reviewed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name=_('Examinée le')),
        ),
        migrations.AlterField(
            model_name='sellerverification',
            name='reviewed_by',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='verifications_reviewed',
                to=settings.AUTH_USER_MODEL,
                verbose_name=_('Examinée par'),
            ),
        ),
        # SellerVerification — Meta
        migrations.AlterModelOptions(
            name='sellerverification',
            options={
                'ordering': ['-created_at'],
                'verbose_name': _('Vérification vendeur'),
                'verbose_name_plural': _('Vérifications vendeurs'),
            },
        ),

        # ══════════════════════════════════════════════════════════════
        # BazarFavori — champs
        # ══════════════════════════════════════════════════════════════
        migrations.AlterField(
            model_name='bazarfavori',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='bazar_favoris',
                to=settings.AUTH_USER_MODEL,
                verbose_name=_('Utilisateur'),
            ),
        ),
        migrations.AlterField(
            model_name='bazarfavori',
            name='annonce',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='favoris',
                to='bazar.annonce',
                verbose_name=_('Annonce'),
            ),
        ),
        migrations.AlterField(
            model_name='bazarfavori',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, verbose_name=_('Ajouté le')),
        ),
        # BazarFavori — Meta
        migrations.AlterModelOptions(
            name='bazarfavori',
            options={
                'ordering': ['-created_at'],
                'verbose_name': _('Favori Bazar'),
                'verbose_name_plural': _('Favoris Bazar'),
            },
        ),
    ]
