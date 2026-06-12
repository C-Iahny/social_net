from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notification', '0002_pushsubscription'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='read',
            field=models.BooleanField(default=False, db_index=True),
        ),
    ]
