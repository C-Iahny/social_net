from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bazar', '0007_alter_verbose_names_i18n'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # seller_type
        migrations.AddField(
            model_name='sellerverification',
            name='seller_type',
            field=models.CharField(
                choices=[('verified', 'Vendeur Vérifié'), ('pro', 'Concessionnaire / Boutique Pro')],
                default='verified',
                max_length=10,
                db_index=True,
                verbose_name='Type de vendeur',
            ),
        ),
        # boutique_name
        migrations.AddField(
            model_name='sellerverification',
            name='boutique_name',
            field=models.CharField(blank=True, default='', max_length=120, verbose_name='Nom de la boutique'),
        ),
        # boutique_description
        migrations.AddField(
            model_name='sellerverification',
            name='boutique_description',
            field=models.TextField(blank=True, default='', verbose_name='Description de la boutique'),
        ),
        # boutique_category
        migrations.AddField(
            model_name='sellerverification',
            name='boutique_category',
            field=models.CharField(
                blank=True, default='', max_length=20,
                choices=[
                    ('auto',         'Automobile & Moto'),
                    ('electronique', 'Électronique & Informatique'),
                    ('mode',         'Mode & Vêtements'),
                    ('maison',       'Maison & Mobilier'),
                    ('alimentation', 'Alimentation & Boissons'),
                    ('materiaux',    'Matériaux & BTP'),
                    ('agriculture',  'Agriculture & Élevage'),
                    ('immobilier',   'Immobilier'),
                    ('services',     'Services & Prestations'),
                    ('autre',        'Autre'),
                ],
                verbose_name='Catégorie principale',
            ),
        ),
        # boutique_phone
        migrations.AddField(
            model_name='sellerverification',
            name='boutique_phone',
            field=models.CharField(blank=True, default='', max_length=30, verbose_name='Téléphone boutique (WhatsApp)'),
        ),
        # boutique_address
        migrations.AddField(
            model_name='sellerverification',
            name='boutique_address',
            field=models.CharField(blank=True, default='', max_length=250, verbose_name='Adresse / Localisation'),
        ),
        # boutique_hours
        migrations.AddField(
            model_name='sellerverification',
            name='boutique_hours',
            field=models.CharField(
                blank=True, default='', max_length=250,
                verbose_name='Horaires',
                help_text='Ex : Lun–Sam 8h–18h',
            ),
        ),
        # boutique_banner
        migrations.AddField(
            model_name='sellerverification',
            name='boutique_banner',
            field=models.ImageField(blank=True, null=True, upload_to='bazar/boutiques/%Y/%m/', verbose_name='Bannière boutique'),
        ),
        # approved_at
        migrations.AddField(
            model_name='sellerverification',
            name='approved_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Approuvé le'),
        ),
        # free_until
        migrations.AddField(
            model_name='sellerverification',
            name='free_until',
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name="Gratuit jusqu'au",
                help_text='Date de fin de la période gratuite (1 an après approbation).',
            ),
        ),
    ]
