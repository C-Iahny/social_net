import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Annonce',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=180, verbose_name='Titre')),
                ('description', models.TextField(verbose_name='Description')),
                ('category', models.CharField(
                    choices=[
                        ('electronique',  'Électronique & Téléphones'),
                        ('vehicules',     'Véhicules & Motos'),
                        ('immobilier',    'Immobilier & Location'),
                        ('mode',          'Mode & Vêtements'),
                        ('maison',        'Maison & Mobilier'),
                        ('agriculture',   'Agriculture & Élevage'),
                        ('alimentaire',   'Alimentaire & Boissons'),
                        ('services',      'Services & Prestations'),
                        ('emploi',        'Emploi & Formation'),
                        ('artisanat',     'Artisanat & Art'),
                        ('sports',        'Sports & Loisirs'),
                        ('bebe',          'Bébé & Enfants'),
                        ('autres',        'Autres'),
                    ],
                    default='autres', max_length=30, verbose_name='Catégorie',
                )),
                ('condition', models.CharField(
                    choices=[
                        ('neuf',      'Neuf'),
                        ('tres_bon',  'Très bon état'),
                        ('bon',       'Bon état'),
                        ('correct',   'État correct'),
                        ('pieces',    'Pour pièces'),
                    ],
                    default='bon', max_length=20, verbose_name='État',
                )),
                ('price', models.DecimalField(
                    blank=True, decimal_places=0, max_digits=12, null=True,
                    verbose_name='Prix (Ar)',
                    help_text='Laisser vide pour "Prix à discuter"',
                )),
                ('price_negotiable', models.BooleanField(default=False, verbose_name='Prix négociable')),
                ('location', models.CharField(
                    max_length=120, verbose_name='Localisation',
                    help_text='Ville / quartier (ex: Antananarivo, Analakely)',
                )),
                ('contact_phone', models.CharField(
                    blank=True, default='', max_length=20, verbose_name='Téléphone / WhatsApp',
                )),
                ('show_phone', models.BooleanField(default=True, verbose_name='Afficher le numéro publiquement')),
                ('status', models.CharField(
                    choices=[
                        ('active',  'Active'),
                        ('vendue',  'Vendue'),
                        ('pause',   'En pause'),
                        ('expiree', 'Expirée'),
                    ],
                    default='active', max_length=10, verbose_name='Statut',
                )),
                ('views_count', models.PositiveIntegerField(default=0, verbose_name='Vues')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('seller', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='annonces',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Vendeur',
                )),
            ],
            options={
                'verbose_name': 'Annonce',
                'verbose_name_plural': 'Annonces',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AnnonceImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='bazar/annonces/%Y/%m/', verbose_name='Image')),
                ('is_primary', models.BooleanField(default=False, verbose_name='Photo principale')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')),
                ('annonce', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='images',
                    to='bazar.annonce',
                    verbose_name='Annonce',
                )),
            ],
            options={
                'verbose_name': "Photo d'annonce",
                'verbose_name_plural': "Photos d'annonce",
                'ordering': ['is_primary', 'order'],
            },
        ),
        migrations.AddIndex(
            model_name='annonce',
            index=models.Index(fields=['-created_at'], name='bazar_annonce_created_idx'),
        ),
        migrations.AddIndex(
            model_name='annonce',
            index=models.Index(fields=['category', '-created_at'], name='bazar_annonce_cat_idx'),
        ),
        migrations.AddIndex(
            model_name='annonce',
            index=models.Index(fields=['seller', '-created_at'], name='bazar_annonce_seller_idx'),
        ),
        migrations.AddIndex(
            model_name='annonce',
            index=models.Index(fields=['status'], name='bazar_annonce_status_idx'),
        ),
    ]
