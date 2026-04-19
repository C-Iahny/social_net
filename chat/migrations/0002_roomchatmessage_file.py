from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0001_initial'),
    ]

    operations = [
        # Make content optional (blank=True) for file-only messages
        migrations.AlterField(
            model_name='roomchatmessage',
            name='content',
            field=models.TextField(blank=True, default=''),
        ),
        # File attachment
        migrations.AddField(
            model_name='roomchatmessage',
            name='file',
            field=models.FileField(blank=True, null=True, upload_to='chat_files/'),
        ),
        # File type tag: 'image' | 'video' | 'document' | ''
        migrations.AddField(
            model_name='roomchatmessage',
            name='file_type',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
    ]
