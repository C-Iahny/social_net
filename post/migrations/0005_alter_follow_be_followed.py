# Correction du related_name mal orthographié : 'be_follwed' → 'be_followed'
# Pas de changement SQL (related_name est purement Python), mais Django l'exige
# pour que l'état des migrations corresponde au modèle actuel.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('post', '0004_alter_comment_id'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='follow',
            name='user_follower',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='be_followed',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
