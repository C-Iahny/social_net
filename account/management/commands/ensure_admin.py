import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.db import IntegrityError


class Command(BaseCommand):
    help = "Crée ou met à jour le superutilisateur depuis les variables d'environnement (idempotent)"

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.environ.get('ADMIN_USERNAME', 'admin')
        email    = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
        password = os.environ.get('ADMIN_PASSWORD', '')

        if not password:
            self.stderr.write("ADMIN_PASSWORD non défini — commande ignorée.")
            return

        # Supprimer les utilisateurs corrompus (email sans '@', créés par des anciennes commandes)
        broken_qs = User.objects.filter(~Q(email__contains='@'))
        if broken_qs.exists():
            count = broken_qs.count()
            broken_qs.delete()
            self.stdout.write(f"{count} utilisateur(s) corrompu(s) supprimé(s).")

        # Si l'utilisateur existe déjà, on met à jour son mot de passe et ses droits
        existing = User.objects.filter(email=email).first()
        if existing:
            existing.set_password(password)
            existing.is_superuser = True
            existing.is_staff = True
            existing.is_admin = True
            existing.save()
            self.stdout.write(self.style.SUCCESS(f"Superutilisateur '{email}' mis à jour."))
            return

        # Sinon on le crée
        try:
            User.objects.create_superuser(email=email, username=username, password=password)
            self.stdout.write(self.style.SUCCESS(f"Superutilisateur '{email}' créé avec succès."))
        except IntegrityError as e:
            self.stderr.write(f"Erreur lors de la création : {e}")
