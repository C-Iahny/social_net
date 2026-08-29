"""
Aligne le texte du Hero sur la maquette retenue.

Même situation qu'en 0008 pour les couleurs : changer le `default` du modèle
(migration 0009) ne touche pas la ligne déjà enregistrée. La landing afficherait
donc l'ancienne accroche dans la nouvelle typographie.

La réécriture est conditionnelle : elle ne s'applique que si le texte est encore
celui d'origine. Un titre ou une accroche saisis depuis l'admin sont laissés
intacts, y compris si la migration est rejouée.
"""
from django.db import migrations


LEGACY_TITLE = "Connectez-vous.\nPartagez. Grandissez."
LEGACY_SUBTITLE = (
    "Si vous connaissez ce que c'est Vazimba et que vous en êtes un(e), alors "
    "vous êtes au bon endroit car cette plateforme est conçue pour les Vazimba. "
    "Pour un partage d'idées, de messages et d'informations en temps réel."
)

NEW_TITLE = "Le réseau social qui parle *malagasy*."
NEW_SUBTITLE = (
    "Un fil d'actualité, une place de marché et un guide du pays — au même endroit."
)


def appliquer(apps, schema_editor):
    HeroSettings = apps.get_model('personal', 'HeroSettings')
    for hero in HeroSettings.objects.all():
        maj = {}
        if hero.title.strip() == LEGACY_TITLE.strip():
            maj['title'] = NEW_TITLE
        if hero.subtitle.strip() == LEGACY_SUBTITLE.strip():
            maj['subtitle'] = NEW_SUBTITLE
        if maj:
            HeroSettings.objects.filter(pk=hero.pk).update(**maj)


def revenir(apps, schema_editor):
    """Restaure l'accroche d'origine, pour que la migration soit réversible."""
    HeroSettings = apps.get_model('personal', 'HeroSettings')
    HeroSettings.objects.filter(title=NEW_TITLE).update(title=LEGACY_TITLE)
    HeroSettings.objects.filter(subtitle=NEW_SUBTITLE).update(subtitle=LEGACY_SUBTITLE)


class Migration(migrations.Migration):

    dependencies = [
        ('personal', '0009_alter_herosettings_subtitle_alter_herosettings_title'),
    ]

    operations = [
        migrations.RunPython(appliquer, revenir),
    ]
