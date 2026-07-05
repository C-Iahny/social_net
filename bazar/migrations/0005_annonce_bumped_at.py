from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bazar', '0004_annonce_region'),
    ]

    operations = [
        migrations.AddField(
            model_name='annonce',
            name='bumped_at',
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                default=None,
                help_text="Date du dernier bump — utilisé pour remonter en tête de liste (1 fois / 24h).",
                null=True,
                verbose_name='Rafraîchi le',
            ),
        ),
    ]
