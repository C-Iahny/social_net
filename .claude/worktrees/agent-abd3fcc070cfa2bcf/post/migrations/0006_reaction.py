import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('post', '0005_alter_follow_be_followed'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Reaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reaction_type', models.CharField(
                    choices=[
                        ('like',  '👍'),
                        ('heart', '❤️'),
                        ('laugh', '😂'),
                        ('wow',   '😮'),
                        ('sad',   '😢'),
                    ],
                    default='like',
                    max_length=10,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('post', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reactions',
                    to='post.post',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['created_at'],
                'unique_together': {('post', 'user')},
            },
        ),
    ]
