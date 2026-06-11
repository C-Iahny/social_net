from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('post', '0014_post_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='reveal_date',
            field=models.DateTimeField(
                null=True, blank=True,
                verbose_name='Date de révélation',
                help_text='Pour les Capsules Vintana : date à laquelle le contenu devient visible.',
            ),
        ),
        migrations.AlterField(
            model_name='post',
            name='post_type',
            field=models.CharField(
                max_length=10,
                choices=[
                    ('default', 'Post standard'),
                    ('kabary',  'Kabary numérique'),
                    ('vintana', 'Capsule Vintana'),
                ],
                default='default',
                verbose_name='Type de post',
            ),
        ),
    ]
