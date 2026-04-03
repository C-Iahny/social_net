# Migration corrigée : ProfileImageField a été supprimé du modèle.
# On utilise models.ImageField standard, identique à l'état réel du modèle.

import account.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='account',
            name='profile_image',
            field=models.ImageField(
                blank=True,
                default=account.models.get_default_profile_image,
                max_length=255,
                null=True,
                upload_to=account.models.get_profile_image_filepath,
            ),
        ),
    ]
