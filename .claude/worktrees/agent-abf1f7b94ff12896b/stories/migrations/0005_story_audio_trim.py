from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stories', '0004_story_audio'),
    ]

    operations = [
        migrations.AddField(
            model_name='story',
            name='audio_trim_start',
            field=models.FloatField(default=0.0, help_text='Début du clip (secondes)'),
        ),
    ]
