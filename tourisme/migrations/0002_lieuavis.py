from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tourisme', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LieuAvis',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveSmallIntegerField(
                    choices=[(1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5')],
                    default=5, verbose_name='Note (1-5)')),
                ('comment', models.TextField(verbose_name='Commentaire')),
                ('visited_at', models.DateField(blank=True, null=True, verbose_name='Date de visite')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('author', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='avis_tourisme',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Auteur',
                )),
                ('lieu', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='avis',
                    to='tourisme.lieutouristique',
                    verbose_name='Lieu',
                )),
            ],
            options={
                'verbose_name': 'Avis',
                'verbose_name_plural': 'Avis',
                'ordering': ['-created_at'],
                'unique_together': {('lieu', 'author')},
            },
        ),
    ]
