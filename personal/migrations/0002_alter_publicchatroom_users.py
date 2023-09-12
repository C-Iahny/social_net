# Generated by Django 4.2 on 2023-06-17 21:12

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('personal', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='publicchatroom',
            name='users',
            field=models.ManyToManyField(help_text='users who are connected to chat room.', to=settings.AUTH_USER_MODEL),
        ),
    ]
