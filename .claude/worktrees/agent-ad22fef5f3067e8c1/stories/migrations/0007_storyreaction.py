from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('stories', '0006_story_text_color'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='StoryReaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('emoji', models.CharField(
                    choices=[('❤️', 'Cœur'), ('😂', 'Haha'), ('😮', 'Wow'), ('😢', 'Triste'), ('🔥', 'Feu')],
                    max_length=10,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('story', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reactions',
                    to='stories.story',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='story_reactions',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-created_at'],
                'unique_together': {('story', 'user')},
            },
        ),
    ]
