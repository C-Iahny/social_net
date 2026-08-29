import os

from django.core.management.base import BaseCommand
from django.db import IntegrityError


class Command(BaseCommand):
    help = "Crée le superutilisateur depuis les variables d'environnement (idempotent)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-password',
            action='store_true',
            help="Réinitialise le mot de passe du compte s'il existe déjà.",
        )
        parser.add_argument(
            '--purge-invalid-emails',
            action='store_true',
            help="DESTRUCTIF : supprime les comptes dont l'e-mail ne contient pas '@'.",
        )

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        username = os.environ.get('ADMIN_USERNAME', 'admin')
        email    = os.environ.get('ADMIN_EMAIL', '')
        password = os.environ.get('ADMIN_PASSWORD', '')

        if not email:
            self.stderr.write("ADMIN_EMAIL non défini — commande ignorée.")
            return
        if not password:
            self.stderr.write("ADMIN_PASSWORD non défini — commande ignorée.")
            return

        # ── Purge des comptes à e-mail invalide ──────────────────────────────
        # Cette suppression en masse s'exécutait à CHAQUE déploiement (la
        # commande est appelée dans railway.toml) et effaçait définitivement
        # des comptes — et, en cascade, leurs posts, messages et médias.
        # Elle est désormais explicite et manuelle.
        if options['purge_invalid_emails']:
            from django.db.models import Q
            broken_qs = User.objects.filter(~Q(email__contains='@'))
            count = broken_qs.count()
            if count:
                broken_qs.delete()
            self.stdout.write(f"{count} compte(s) à e-mail invalide supprimé(s).")

        existing = User.objects.filter(email__iexact=email).first()
        if existing:
            # Un compte existant n'est PLUS promu superutilisateur en silence :
            # si un utilisateur s'inscrivait avec l'adresse ADMIN_EMAIL, le
            # déploiement suivant lui accordait tous les droits d'administration
            # et réécrivait son mot de passe.
            if not (existing.is_superuser and existing.is_staff):
                self.stderr.write(self.style.WARNING(
                    f"Le compte '{email}' existe mais n'est pas administrateur. "
                    f"Aucune promotion automatique — utilisez l'admin Django ou "
                    f"`manage.py shell` si la promotion est voulue."
                ))
                return

            if options['reset_password']:
                existing.set_password(password)
                existing.save(update_fields=['password'])
                self.stdout.write(self.style.SUCCESS(f"Mot de passe de '{email}' réinitialisé."))
            else:
                self.stdout.write(f"Superutilisateur '{email}' déjà présent — rien à faire.")
            return

        try:
            User.objects.create_superuser(email=email, username=username, password=password)
            self.stdout.write(self.style.SUCCESS(f"Superutilisateur '{email}' créé avec succès."))
        except IntegrityError as e:
            self.stderr.write(f"Erreur lors de la création : {e}")
