from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('post', '0016_post_region'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Report',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_id', models.PositiveIntegerField()),
                ('reason', models.CharField(
                    choices=[
                        ('spam', 'Spam / publicité abusive'),
                        ('hate', 'Discours haineux / harcelement'),
                        ('violence', 'Violence / contenu choquant'),
                        ('nudity', 'Nudité / contenu adulte'),
                        ('false', 'Fausse information'),
                        ('other', 'Autre'),
                    ],
                    max_length=20,
                    verbose_name='Raison',
                )),
                ('comment', models.TextField(blank=True, verbose_name='Commentaire')),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'En attente'),
                        ('reviewed', 'Traité'),
                        ('dismissed', 'Rejeté'),
                    ],
                    default='pending',
                    max_length=20,
                    verbose_name='Statut',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Signalé le')),
                ('reviewed_at', models.DateTimeField(blank=True, null=True, verbose_name='Traité le')),
                ('content_type', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='contenttypes.contenttype',
                )),
                ('reporter', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reports_sent',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Signalé par',
                )),
            ],
            options={
                'verbose_name': 'Signalement',
                'verbose_name_plural': 'Signalements',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='report',
            unique_together={('reporter', 'content_type', 'object_id')},
        ),
    ]
