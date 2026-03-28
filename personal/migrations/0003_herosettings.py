# Hand-written migration — 2026-03-27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('personal', '0002_announcement'),
    ]

    operations = [
        migrations.CreateModel(
            name='HeroSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(
                    default='Explorez la communauté ZOOT',
                    max_length=200,
                    verbose_name='Titre principal (H1)',
                )),
                ('subtitle', models.TextField(
                    default=(
                        'Découvrez des publications, des personnes et des contenus du monde entier. '
                        'Connectez-vous, partagez et inspirez-vous.'
                    ),
                    verbose_name="Texte d'accroche",
                )),
                ('gradient_from', models.CharField(
                    default='#1877f2',
                    help_text='Code couleur hexadécimal, ex. #1877f2',
                    max_length=20,
                    verbose_name='Couleur de début (dégradé)',
                )),
                ('gradient_to', models.CharField(
                    default='#7c3aed',
                    help_text='Code couleur hexadécimal, ex. #7c3aed',
                    max_length=20,
                    verbose_name='Couleur de fin (dégradé)',
                )),
            ],
            options={
                'verbose_name': 'Réglages du Hero',
                'verbose_name_plural': 'Réglages du Hero',
            },
        ),
    ]
