# Generated by Django 4.2 on 2023-07-07 20:20

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('post', '0002_category_delete_likepost_delete_unlikepost_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='post',
            name='likes',
            field=models.ManyToManyField(blank=True, related_name='mksd_event', to=settings.AUTH_USER_MODEL),
        ),
    ]