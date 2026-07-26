from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('post', '0018_post_status_postbookmark'),
    ]

    operations = [
        migrations.AlterField(
            model_name='post',
            name='title',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
