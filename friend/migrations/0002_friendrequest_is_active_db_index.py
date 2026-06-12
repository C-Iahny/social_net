from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('friend', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='friendrequest',
            name='is_active',
            field=models.BooleanField(blank=False, null=False, default=True, db_index=True),
        ),
    ]
