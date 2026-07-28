"""
Migration: corrige l'ordre des photos d'annonce.
ordering = ['-is_primary', 'order']  → photo principale (is_primary=True) en premier.

L'ancien ordering ['is_primary', 'order'] (ascendant) mettait les photos
NON-principales avant la principale (False < True), ce qui était inversé.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bazar', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='annonceimage',
            options={
                'ordering': ['-is_primary', 'order'],
                'verbose_name': "Photo d’annonce",
                'verbose_name_plural': "Photos d’annonce",
            },
        ),
    ]
