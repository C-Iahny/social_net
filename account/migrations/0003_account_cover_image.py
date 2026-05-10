from django.db import migrations, models
from ZOOT.storage import AutoMediaCloudinaryStorage


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0002_profile_image_field_fallback'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='cover_image',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='cover_images/',
                storage=AutoMediaCloudinaryStorage(),
            ),
        ),
    ]
