from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bazar', '0008_sellerverification_boutique'),
    ]

    operations = [
        migrations.AddField(
            model_name='annonce',
            name='listing_type',
            field=models.CharField(
                choices=[('vente', 'Vente'), ('location', 'Location')],
                db_index=True,
                default='vente',
                max_length=10,
                verbose_name="Type d'annonce",
            ),
        ),
        migrations.AddField(
            model_name='annonce',
            name='prix_location',
            field=models.DecimalField(
                blank=True,
                decimal_places=0,
                max_digits=12,
                null=True,
                verbose_name='Prix de location',
            ),
        ),
        migrations.AddField(
            model_name='annonce',
            name='periode_location',
            field=models.CharField(
                blank=True,
                choices=[('jour', '/ jour'), ('semaine', '/ semaine'), ('mois', '/ mois')],
                default='jour',
                max_length=10,
                verbose_name='Période',
            ),
        ),
        migrations.AddField(
            model_name='annonce',
            name='caution',
            field=models.DecimalField(
                blank=True,
                decimal_places=0,
                max_digits=12,
                null=True,
                verbose_name='Caution (Ar)',
            ),
        ),
        migrations.AddField(
            model_name='annonce',
            name='duree_min',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Durée minimale de location en jours',
                null=True,
                verbose_name='Durée min (jours)',
            ),
        ),
        migrations.AddField(
            model_name='annonce',
            name='nb_pieces',
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                verbose_name='Nb de pièces',
            ),
        ),
        migrations.AddField(
            model_name='annonce',
            name='surface_m2',
            field=models.FloatField(
                blank=True,
                null=True,
                verbose_name='Surface (m²)',
            ),
        ),
        migrations.AddField(
            model_name='annonce',
            name='meuble',
            field=models.BooleanField(default=False, verbose_name='Meublé'),
        ),
        migrations.AddField(
            model_name='annonce',
            name='charges_incluses',
            field=models.BooleanField(default=False, verbose_name='Charges incluses'),
        ),
        migrations.AddField(
            model_name='annonce',
            name='avec_chauffeur',
            field=models.BooleanField(default=False, verbose_name='Avec chauffeur'),
        ),
        migrations.AlterField(
            model_name='annonce',
            name='status',
            field=models.CharField(
                choices=[
                    ('active',  'Active'),
                    ('vendue',  'Vendue'),
                    ('louee',   'Louée'),
                    ('pause',   'En pause'),
                    ('expiree', 'Expirée'),
                ],
                default='active',
                max_length=10,
                verbose_name='Statut',
            ),
        ),
    ]
