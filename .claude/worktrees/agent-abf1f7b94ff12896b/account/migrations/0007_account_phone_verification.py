import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0006_account_region'),
    ]

    operations = [
        # ── Champs téléphone sur Account ──────────────────────────────────────
        migrations.AddField(
            model_name='account',
            name='phone_number',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                help_text='Format international : +261 34 XX XXX XX',
                max_length=20,
                verbose_name='Numéro de téléphone',
            ),
        ),
        migrations.AddField(
            model_name='account',
            name='phone_verified',
            field=models.BooleanField(
                default=False,
                help_text='Le numéro a été confirmé par SMS.',
                verbose_name='Téléphone vérifié',
            ),
        ),
        # ── Modèle PhoneVerification ──────────────────────────────────────────
        migrations.CreateModel(
            name='PhoneVerification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone',      models.CharField(max_length=20, verbose_name='Numéro en cours de vérification')),
                ('code',       models.CharField(max_length=6, verbose_name='Code OTP')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('attempts',   models.PositiveSmallIntegerField(default=0, verbose_name='Tentatives')),
                ('verified',   models.BooleanField(default=False, verbose_name='Validé')),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='phone_verifications',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Utilisateur',
                )),
            ],
            options={
                'verbose_name': 'Vérification téléphone',
                'verbose_name_plural': 'Vérifications téléphone',
                'ordering': ['-created_at'],
            },
        ),
    ]
