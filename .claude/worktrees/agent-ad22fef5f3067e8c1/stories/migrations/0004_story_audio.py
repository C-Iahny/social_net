from django.db import migrations, models


def _story_audio_path(instance, filename):
    """Chemin de stockage des fichiers audio — défini localement pour que la
    migration reste stable même si la fonction dans models.py est renommée."""
    return f'stories/audio/{instance.user.id}/{filename}'


class Migration(migrations.Migration):

    dependencies = [
        ('stories', '0003_story_text_position'),
    ]

    operations = [
        migrations.AddField(
            model_name='story',
            name='audio',
            field=models.FileField(blank=True, null=True, upload_to=_story_audio_path),
        ),
        migrations.AddField(
            model_name='story',
            name='audio_type',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
    ]
