from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('post', '0012_hashtag_tag_delete_category_alter_reaction_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='is_pinned',
            field=models.BooleanField(default=False, verbose_name='Épinglé'),
        ),
    ]
