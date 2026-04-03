# Suppression des modèles PublicChatRoom / PublicRoomChatMessage du module personal.
# Ces modèles sont dupliqués : ils existent aussi dans public_chat/models.py
# qui est l'emplacement canonique. On supprime ici les tables personal_*.
# L'ordre est important : supprimer d'abord PublicRoomChatMessage (FK → PublicChatRoom).

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('personal', '0004_herosettings_background_image'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.DeleteModel(name='PublicRoomChatMessage'),
        migrations.DeleteModel(name='PublicChatRoom'),
    ]
