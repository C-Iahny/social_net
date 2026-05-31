from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('post', '0008_postmedia'),
    ]

    operations = [
        migrations.AlterField(
            model_name='postmedia',
            name='file',
            field=models.FileField(upload_to='post_media/'),
        ),
    ]
