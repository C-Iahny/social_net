from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('post', '0007_comment_parent'),
    ]

    operations = [
        migrations.CreateModel(
            name='PostMedia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='post_media/')),
                ('media_type', models.CharField(
                    choices=[('image', 'Image'), ('video', 'Vidéo')],
                    default='image',
                    max_length=10,
                )),
                ('order', models.PositiveIntegerField(default=0)),
                ('post', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='media_files',
                    to='post.post',
                )),
            ],
            options={
                'ordering': ['order'],
            },
        ),
    ]
