from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0002_alter_group_id_alter_groupmembership_id'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Ajoute le rôle modérateur dans GroupMembership
        migrations.AlterField(
            model_name='groupmembership',
            name='role',
            field=models.CharField(
                choices=[('admin', 'Admin'), ('moderator', 'Modérateur'), ('member', 'Membre')],
                default='member',
                max_length=12,
            ),
        ),
        # Nouveau modèle GroupEvent
        migrations.CreateModel(
            name='GroupEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=150, verbose_name='Titre')),
                ('description', models.TextField(blank=True, max_length=1000, verbose_name='Description')),
                ('location', models.CharField(blank=True, max_length=200, verbose_name='Lieu')),
                ('event_date', models.DateTimeField(verbose_name='Date de l\'événement')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('group', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='events',
                    to='group.group',
                )),
                ('organizer', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='organized_events',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('attendees', models.ManyToManyField(
                    blank=True,
                    related_name='attending_events',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['event_date'],
            },
        ),
    ]
