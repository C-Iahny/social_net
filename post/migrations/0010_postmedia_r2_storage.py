from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Retire storage=AutoMediaCloudinaryStorage() du champ PostMedia.file.
    Le stockage est maintenant géré par DEFAULT_FILE_STORAGE (Cloudflare R2).
    """

    dependencies = [
        ('post', '0009_postmedia_auto_storage'),
    ]

    operations = [
        migrations.AlterField(
            model_name='postmedia',
            name='file',
            field=models.FileField(upload_to='post_media/'),
        ),
    ]
