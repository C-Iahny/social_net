"""
Migration: ajoute le modèle SellerVerification.
Vérification vendeur — niveau compte (OneToOne avec AUTH_USER_MODEL).
"""
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bazar', '0002_annonceimage_ordering'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SellerVerification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(
                    choices=[
                        ('pending',  'En attente'),
                        ('approved', 'Approuvé'),
                        ('rejected', 'Refusé'),
                    ],
                    db_index=True,
                    default='pending',
                    max_length=10,
                    verbose_name='Statut',
                )),
                ('message', models.TextField(
                    blank=True,
                    default='',
                    help_text='Pourquoi souhaitez-vous être vérifié ? (facultatif)',
                    verbose_name='Message du vendeur',
                )),
                ('admin_notes', models.TextField(
                    blank=True,
                    default='',
                    verbose_name='Notes admin',
                )),
                ('created_at', models.DateTimeField(
                    auto_now_add=True,
                    verbose_name='Demande le',
                )),
                ('reviewed_at', models.DateTimeField(
                    blank=True,
                    null=True,
                    verbose_name='Examinée le',
                )),
                ('seller', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='seller_verification',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Vendeur',
                )),
                ('reviewed_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='verifications_reviewed',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Examinée par',
                )),
            ],
            options={
                'verbose_name': 'Vérification vendeur',
                'verbose_name_plural': 'Vérifications vendeurs',
                'ordering': ['-created_at'],
            },
        ),
    ]
