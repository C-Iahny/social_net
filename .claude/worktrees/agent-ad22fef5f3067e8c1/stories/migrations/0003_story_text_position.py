"""
Migration : ajout des champs text_x et text_y pour le positionnement libre
du texte dans les stories de type 'text' et 'image_text'.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stories', '0002_story_link'),
    ]

    operations = [
        migrations.AddField(
            model_name='story',
            name='text_x',
            field=models.FloatField(
                default=50.0,
                help_text='Position horizontale du texte (% depuis la gauche)',
            ),
        ),
        migrations.AddField(
            model_name='story',
            name='text_y',
            field=models.FloatField(
                default=50.0,
                help_text='Position verticale du texte (% depuis le haut)',
            ),
        ),
    ]
