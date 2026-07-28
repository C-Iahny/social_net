from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stories', '0005_story_audio_trim'),
    ]

    operations = [
        migrations.AddField(
            model_name='story',
            name='text_color',
            field=models.CharField(
                blank=True, default='#ffffff', max_length=20,
                help_text='Couleur CSS du texte overlay'
            ),
        ),
    ]
