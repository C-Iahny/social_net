from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0004_account_cover_image_r2'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='cgu_accepted_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='CGU & confidentialité acceptées le',
            ),
        ),
    ]
