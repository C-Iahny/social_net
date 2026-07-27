from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('video', '0001_initial')]
    operations = [
        migrations.AddField(model_name='liveroom', name='replay_url',
                            field=models.URLField(max_length=500, blank=True, default='')),
        migrations.AddField(model_name='liveroom', name='replay_available',
                            field=models.BooleanField(default=False)),
    ]
