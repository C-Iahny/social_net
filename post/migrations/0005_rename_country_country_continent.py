# Generated by Django 4.2 on 2023-07-08 18:46

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('post', '0004_continent_country'),
    ]

    operations = [
        migrations.RenameField(
            model_name='country',
            old_name='country',
            new_name='continent',
        ),
    ]