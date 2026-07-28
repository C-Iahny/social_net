from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0003_groupmembership_moderator_groupevent'),
    ]

    operations = [
        migrations.AddField(
            model_name='group',
            name='dina',
            field=models.TextField(
                blank=True,
                default='',
                verbose_name='Dina',
                help_text='Charte communautaire du groupe (règles, engagements, traditions)',
            ),
        ),
    ]
