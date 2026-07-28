from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0002_roomchatmessage_file'),
    ]

    operations = [
        migrations.AddField(
            model_name='roomchatmessage',
            name='reply_to',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='replies',
                to='chat.roomchatmessage',
            ),
        ),
    ]
