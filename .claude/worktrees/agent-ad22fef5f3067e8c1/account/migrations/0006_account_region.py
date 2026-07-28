from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0005_account_cgu_accepted_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='region',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                help_text='Région de Madagascar (pour le filtre "Près de chez moi")',
                max_length=30,
                verbose_name='Région',
            ),
        ),
    ]
