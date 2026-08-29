"""
Bascule le dégradé du hero vers la charte acajou.

Changer le `default` du modèle (migration 0007) ne touche pas la ligne déjà
enregistrée : HeroSettings est un singleton créé au premier appel, et sa ligne
conserve les couleurs de l'ancienne charte indigo/violet. Le hero de la page
d'accueil restait donc bleu-violet au milieu d'une page acajou.

Cette migration ne réécrit la ligne que si ses couleurs figurent encore parmi
les valeurs héritées listées ci-dessous. Un réglage choisi délibérément depuis
l'admin (toute autre valeur) est laissé intact — et le restera si la migration
est rejouée.
"""
from django.db import migrations


# Couleurs de l'ancienne charte : anciens défauts du modèle, plus la variante
# violette effectivement enregistrée en production.
LEGACY_FROM = {'#1877f2', '#1877F2'}
LEGACY_TO   = {'#6c2bd9', '#6C2BD9', '#7c3aed', '#7C3AED'}

NEW_FROM = '#5c2a08'
NEW_TO   = '#A0522D'


def appliquer_acajou(apps, schema_editor):
    HeroSettings = apps.get_model('personal', 'HeroSettings')
    for hero in HeroSettings.objects.all():
        champs = []
        if hero.gradient_from in LEGACY_FROM:
            hero.gradient_from = NEW_FROM
            champs.append('gradient_from')
        if hero.gradient_to in LEGACY_TO:
            hero.gradient_to = NEW_TO
            champs.append('gradient_to')
        if champs:
            # save() du modèle force pk=1 ; ici on est sur le modèle
            # historique, donc un update ciblé suffit.
            HeroSettings.objects.filter(pk=hero.pk).update(
                **{c: getattr(hero, c) for c in champs}
            )


def revenir_indigo(apps, schema_editor):
    """Restaure l'ancien dégradé, pour que la migration soit réversible."""
    HeroSettings = apps.get_model('personal', 'HeroSettings')
    HeroSettings.objects.filter(
        gradient_from=NEW_FROM, gradient_to=NEW_TO,
    ).update(gradient_from='#1877f2', gradient_to='#6c2bd9')


class Migration(migrations.Migration):

    dependencies = [
        ('personal', '0007_alter_herosettings_gradient_from_and_more'),
    ]

    operations = [
        migrations.RunPython(appliquer_acajou, revenir_indigo),
    ]
