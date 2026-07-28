from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('post', '0017_report'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── Champs status + scheduled_at sur Post ─────────────────────────
        migrations.AddField(
            model_name='post',
            name='status',
            field=models.CharField(
                choices=[('published', 'Publié'), ('draft', 'Brouillon'), ('scheduled', 'Programmé')],
                db_index=True,
                default='published',
                max_length=10,
                verbose_name='Statut',
            ),
        ),
        migrations.AddField(
            model_name='post',
            name='scheduled_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Date de publication programmée',
                help_text='Laissez vide pour publier immédiatement.',
            ),
        ),
        # ── Modèle PostBookmark ───────────────────────────────────────────
        migrations.CreateModel(
            name='PostBookmark',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('post', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='bookmarks',
                    to='post.post',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='post_bookmarks',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Post sauvegardé',
                'verbose_name_plural': 'Posts sauvegardés',
                'ordering': ['-created_at'],
                'unique_together': {('user', 'post')},
            },
        ),
    ]
