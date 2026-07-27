from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('post', '0019_post_title_optional'),
        ('tourisme', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='lieu',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='posts',
                to='tourisme.lieutouristique',
                verbose_name='Lieu touristique lié',
            ),
        ),
    ]
