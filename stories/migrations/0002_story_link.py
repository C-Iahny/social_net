from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stories', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='story',
            name='link',
            field=models.URLField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='story',
            name='link_label',
            field=models.CharField(blank=True, default='', max_length=60, verbose_name='Texte du bouton'),
        ),
    ]
