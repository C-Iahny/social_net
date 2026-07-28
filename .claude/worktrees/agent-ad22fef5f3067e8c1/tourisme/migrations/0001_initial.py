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
            name='LieuTouristique',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Nom du lieu')),
                ('slug', models.SlugField(blank=True, max_length=220, unique=True)),
                ('description', models.TextField(verbose_name='Description')),
                ('category', models.CharField(
                    choices=[
                        ('nature', 'Nature & Paysages'),
                        ('plage', 'Plages & Côtes'),
                        ('histoire', 'Histoire & Culture'),
                        ('faune', 'Faune & Parcs naturels'),
                        ('montagne', 'Montagnes & Randonnées'),
                        ('circuit', 'Circuits & Routes'),
                        ('ville', 'Villes & Villages'),
                        ('aventure', 'Aventure & Sport'),
                    ],
                    default='nature',
                    max_length=20,
                    verbose_name='Catégorie',
                )),
                ('region', models.CharField(
                    blank=True,
                    choices=[
                        ('analamanga', 'Analamanga'),
                        ('vakinankaratra', 'Vakinankaratra'),
                        ('itasy', 'Itasy'),
                        ('bongolava', 'Bongolava'),
                        ('haute_matsiatra', 'Haute Matsiatra'),
                        ('amoron_maniana', "Amoron'i Mania"),
                        ('vatovavy', 'Vatovavy'),
                        ('fitovinany', 'Fitovinany'),
                        ('atsimo_atsinanana', 'Atsimo-Atsinanana'),
                        ('atsinanana', 'Atsinanana'),
                        ('analanjirofo', 'Analanjirofo'),
                        ('alaotra_mangoro', 'Alaotra Mangoro'),
                        ('boeny', 'Boeny'),
                        ('sofia', 'Sofia'),
                        ('betsiboka', 'Betsiboka'),
                        ('melaky', 'Melaky'),
                        ('atsimo_andrefana', 'Atsimo-Andrefana'),
                        ('androy', 'Androy'),
                        ('anosy', 'Anosy'),
                        ('menabe', 'Menabe'),
                        ('diana', 'Diana'),
                        ('sava', 'SAVA'),
                    ],
                    db_index=True,
                    default='',
                    max_length=30,
                    verbose_name='Région',
                )),
                ('address', models.CharField(blank=True, default='', max_length=250, verbose_name='Adresse / GPS')),
                ('best_period', models.CharField(blank=True, default='', max_length=120, verbose_name='Meilleure période pour visiter')),
                ('entry_fee', models.CharField(blank=True, default='', max_length=80, verbose_name='Entrée / Tarif')),
                ('tips', models.TextField(blank=True, default='', verbose_name='Conseils pratiques')),
                ('is_approved', models.BooleanField(db_index=True, default=False, verbose_name='Approuvé')),
                ('views_count', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('added_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='lieux_ajoutes',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Lieu touristique',
                'verbose_name_plural': 'Lieux touristiques',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='LieuImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='tourisme/lieux/%Y/%m/')),
                ('caption', models.CharField(blank=True, default='', max_length=200)),
                ('is_primary', models.BooleanField(default=False)),
                ('order', models.PositiveSmallIntegerField(default=0)),
                ('lieu', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='images',
                    to='tourisme.lieutouristique',
                )),
            ],
            options={
                'ordering': ['-is_primary', 'order'],
            },
        ),
        migrations.CreateModel(
            name='GuideTouristique',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bio', models.TextField(verbose_name='Présentation / Bio')),
                ('languages', models.CharField(
                    blank=True,
                    default='',
                    help_text='Ex: Malagasy, Français, Anglais',
                    max_length=250,
                    verbose_name='Langues parlées',
                )),
                ('regions_covered', models.TextField(blank=True, default='', verbose_name='Régions couvertes')),
                ('transport_modes', models.CharField(
                    blank=True,
                    default='',
                    help_text='Ex: Voiture, 4×4, Pirogue',
                    max_length=250,
                    verbose_name='Moyens de déplacement',
                )),
                ('specialities', models.CharField(
                    blank=True,
                    default='',
                    help_text='Ex: Faune, Randonnée, Culturel',
                    max_length=250,
                    verbose_name='Spécialités / Types de circuit',
                )),
                ('conditions', models.TextField(
                    blank=True,
                    default='',
                    help_text='Prix journalier, inclusions, exclusions…',
                    verbose_name='Conditions & Tarifs',
                )),
                ('prix_jour', models.DecimalField(
                    blank=True,
                    decimal_places=0,
                    max_digits=10,
                    null=True,
                    verbose_name='Prix indicatif / jour (Ar)',
                )),
                ('phone', models.CharField(blank=True, default='', max_length=30, verbose_name='Téléphone / WhatsApp')),
                ('years_experience', models.PositiveSmallIntegerField(default=0, verbose_name="Années d'expérience")),
                ('max_group_size', models.PositiveSmallIntegerField(default=10, verbose_name='Taille max du groupe')),
                ('photo', models.ImageField(blank=True, null=True, upload_to='tourisme/guides/%Y/%m/', verbose_name='Photo')),
                ('is_verified', models.BooleanField(db_index=True, default=False, verbose_name='Guide vérifié')),
                ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='Disponible')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('lieux_favoris', models.ManyToManyField(
                    blank=True,
                    related_name='guides',
                    to='tourisme.lieutouristique',
                    verbose_name='Lieux couverts',
                )),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='guide_profile',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Utilisateur',
                )),
            ],
            options={
                'verbose_name': 'Guide touristique',
                'verbose_name_plural': 'Guides touristiques',
                'ordering': ['-is_verified', '-created_at'],
            },
        ),
    ]
