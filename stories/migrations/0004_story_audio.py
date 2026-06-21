from django.db import migrations, models
import stories.models


class Migration(migrations.Migration):

    dependencies = [
        ('stories', '0003_story_text_position'),
    ]

    operations = [
        migrations.AddField(
            model_name='story',
            name='audio',
            field=models.FileField(blank=True, null=True, upload_to=stories.models.story_audio_path),
        ),
        migrations.AddField(
            model_name='story',
            name='audio_type',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
    ]
