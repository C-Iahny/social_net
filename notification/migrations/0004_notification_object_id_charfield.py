from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notification', '0003_notification_read_db_index'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='object_id',
            field=models.CharField(max_length=255),
        ),
    ]
