from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('post', '0013_post_is_pinned'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='post_type',
            field=models.CharField(
                max_length=10,
                choices=[('default', 'Post standard'), ('kabary', 'Kabary numérique')],
                default='default',
                verbose_name='Type de post',
            ),
        ),
    ]
