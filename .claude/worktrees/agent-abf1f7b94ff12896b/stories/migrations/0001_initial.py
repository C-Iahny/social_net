from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import stories.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Story',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('story_type', models.CharField(
                    choices=[('image','Image'),('video','Vidéo'),('text','Texte seul'),('image_text','Image + texte')],
                    default='image', max_length=12,
                )),
                ('media', models.FileField(blank=True, null=True, upload_to=stories.models.story_media_path)),
                ('media_type', models.CharField(blank=True, default='', max_length=8)),
                ('caption', models.CharField(blank=True, default='', max_length=200)),
                ('bg_gradient', models.CharField(
                    blank=True,
                    choices=[('grad_cyan','Cyan → Bleu'),('grad_purple','Violet → Rose'),
                             ('grad_sunset','Orange → Rose'),('grad_forest','Vert → Cyan'),
                             ('grad_night','Nuit → Violet'),('grad_gold','Or → Orange')],
                    default='grad_cyan', max_length=20,
                )),
                ('text_align', models.CharField(
                    choices=[('left','Gauche'),('center','Centre'),('right','Droite')],
                    default='center', max_length=10,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='stories',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-created_at'], 'verbose_name': 'Story', 'verbose_name_plural': 'Stories'},
        ),
        migrations.CreateModel(
            name='StoryView',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('viewed_at', models.DateTimeField(auto_now_add=True)),
                ('story', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='views',
                    to='stories.story',
                )),
                ('viewer', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='story_views',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-viewed_at']},
        ),
        migrations.AlterUniqueTogether(
            name='storyview',
            unique_together={('story', 'viewer')},
        ),
    ]
