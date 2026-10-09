"""
Bascule le dégradé du hero vers la palette lagon.

Même logique que la migration 0008 : la ligne singleton de HeroSettings n'est
réécrite que si elle porte encore les couleurs de la charte acajou (défauts
posés par 0008). Un dégradé choisi délibérément depuis l'admin est conservé.
"""
from django.db import migrations, models


LEGACY_FROM = {'#5c2a08', '#5C2A08'}
LEGACY_TO = {'#A0522D', '#a0522d'}

NEW_FROM = '#115e59'
NEW_TO = '#0891b2'


def appliquer_lagon(apps, schema_editor):
    HeroSettings = apps.get_model('personal', 'HeroSettings')
    for hero in HeroSettings.objects.all():
        champs = {}
        if hero.gradient_from in LEGACY_FROM:
            champs['gradient_from'] = NEW_FROM
        if hero.gradient_to in LEGACY_TO:
            champs['gradient_to'] = NEW_TO
        if champs:
            HeroSettings.objects.filter(pk=hero.pk).update(**champs)


def revenir_acajou(apps, schema_editor):
    HeroSettings = apps.get_model('personal', 'HeroSettings')
    HeroSettings.objects.filter(
        gradient_from=NEW_FROM, gradient_to=NEW_TO,
    ).update(gradient_from='#5c2a08', gradient_to='#A0522D')


class Migration(migrations.Migration):

    dependencies = [
        ('personal', '0010_hero_texte_maquette'),
    ]

    operations = [
        migrations.AlterField(
            model_name='herosettings',
            name='gradient_from',
            field=models.CharField(
                default='#115e59',
                help_text='Code couleur hexadécimal, ex. #115e59',
                max_length=20,
                verbose_name='Couleur de début (dégradé)',
            ),
        ),
        migrations.AlterField(
            model_name='herosettings',
            name='gradient_to',
            field=models.CharField(
                default='#0891b2',
                help_text='Code couleur hexadécimal, ex. #0891b2',
                max_length=20,
                verbose_name='Couleur de fin (dégradé)',
            ),
        ),
        migrations.RunPython(appliquer_lagon, revenir_acajou),
    ]
