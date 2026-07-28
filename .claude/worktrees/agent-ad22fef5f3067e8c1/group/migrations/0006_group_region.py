from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0005_group_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='group',
            name='region',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                help_text='Région de Madagascar (pour le filtre "Groupes locaux")',
                max_length=30,
                verbose_name='Région',
            ),
        ),
    ]
