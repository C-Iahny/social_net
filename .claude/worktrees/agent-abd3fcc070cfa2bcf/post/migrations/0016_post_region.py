from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('post', '0015_post_reveal_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='region',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                help_text="Région de Madagascar du post (auto-remplie depuis le profil de l'auteur)",
                max_length=30,
                verbose_name='Région',
            ),
        ),
    ]
