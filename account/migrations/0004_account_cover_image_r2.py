from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0003_account_cover_image'),
    ]

    operations = [
        migrations.AlterField(
            model_name='account',
            name='cover_image',
            field=models.ImageField(blank=True, null=True, upload_to='cover_images/'),
        ),
    ]
