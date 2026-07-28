# Hand-written migration — 2026-03-27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('personal', '0003_herosettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='herosettings',
            name='background_image',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='hero_bg/',
                verbose_name='Image de fond (optionnel)',
                help_text='Si renseignée, s\'affiche derrière le dégradé (qui devient un calque semi-transparent).',
            ),
        ),
    ]
