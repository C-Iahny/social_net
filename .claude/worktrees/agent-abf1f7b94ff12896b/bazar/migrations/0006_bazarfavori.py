from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bazar', '0005_annonce_bumped_at'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BazarFavori',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Ajouté le')),
                ('annonce', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='favoris',
                    to='bazar.annonce',
                    verbose_name='Annonce',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='bazar_favoris',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Utilisateur',
                )),
            ],
            options={
                'verbose_name': 'Favori Bazar',
                'verbose_name_plural': 'Favoris Bazar',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='bazarfavori',
            unique_together={('user', 'annonce')},
        ),
    ]
