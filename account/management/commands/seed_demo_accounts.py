"""
seed_demo_accounts — crée (ou supprime) des comptes de démonstration reconnaissables.

    python manage.py seed_demo_accounts 500            # crée 500 comptes
    python manage.py seed_demo_accounts 500 --region analamanga
    python manage.py seed_demo_accounts --list         # compte / liste les comptes démo
    python manage.py seed_demo_accounts --purge        # supprime TOUS les comptes démo
    python manage.py seed_demo_accounts --purge 50     # supprime 50 comptes démo (les plus anciens)

Tous les comptes créés ont une adresse @demo.vazimba.io : c'est ce qui permet de
les retrouver et de les supprimer sans toucher aux vrais comptes. Mot de passe
inutilisable (personne ne peut s'y connecter), bio et région plausibles.
"""
import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction
from django.utils import timezone

DEMO_DOMAIN = 'demo.vazimba.io'

PRENOMS = [
    'Tiana', 'Hery', 'Miora', 'Rado', 'Fara', 'Naina', 'Lova', 'Toky', 'Sitraka', 'Hanta',
    'Mamy', 'Nirina', 'Fanja', 'Rija', 'Tahina', 'Vola', 'Zo', 'Haja', 'Feno', 'Ando',
    'Njaka', 'Sariaka', 'Tojo', 'Mialy', 'Faly', 'Hasina', 'Onja', 'Dina', 'Lalaina', 'Koto',
    'Soa', 'Tsiory', 'Mahefa', 'Fitiavana', 'Aina', 'Nomena', 'Santatra', 'Voahangy', 'Tantely', 'Riana',
    'Jean', 'Marie', 'Patrick', 'Sylvie', 'Eric', 'Nadia', 'Olivier', 'Sandra', 'Tovo', 'Bako',
]
NOMS = [
    'Rakoto', 'Rabe', 'Randria', 'Razafy', 'Rasoa', 'Andrianina', 'Ramanantsoa', 'Rajaonarison',
    'Rasolofo', 'Ravelo', 'Raharison', 'Ranaivo', 'Andriamanana', 'Rafaralahy', 'Razanadrakoto',
    'Rakotomalala', 'Ratsimbazafy', 'Andrianarivo', 'Rasoanaivo', 'Raveloson', 'Rakotondrabe',
    'Ramiandrisoa', 'Randrianarisoa', 'Andriamahefa', 'Rabemananjara', 'Ratovo', 'Razanamparany',
]
VILLES = {
    'analamanga': ['Antananarivo', 'Analakely', 'Ankorondrano', 'Ivandry', 'Ambohimanarina', 'Itaosy', 'Ambatobe'],
    'vakinankaratra': ['Antsirabe', 'Betafo'],
    'atsinanana': ['Toamasina', 'Tamatave'],
    'boeny': ['Mahajanga'],
    'atsimo_andrefana': ['Toliara'],
    'haute_matsiatra': ['Fianarantsoa'],
    'diana': ['Antsiranana', 'Nosy Be'],
    'sava': ['Sambava', 'Antalaha'],
    'alaotra_mangoro': ['Ambatondrazaka', 'Moramanga'],
    'menabe': ['Morondava'],
}
BIOS = [
    'Mpankafy sakafo malagasy 🍛', 'Toujours à la recherche du meilleur mofo gasy', 'Tanà, vary sy loaka ❤️',
    'Étudiant·e, fan de foot et de zebu', 'Vendeur au bazar le week-end', 'Photographe amateur, coucher de soleil sur Anosy',
    'Mpanjifa mahatoky 😉', 'Livreur moto, ponctuel', 'Maman de deux enfants, cuisine maison', 'Développeur web à Ivandry',
    'Fan de Mahaleo et de basket', 'Toujours partant pour un pique-nique à Ambohimanga', '', '', '',
]


class Command(BaseCommand):
    help = 'Crée ou supprime des comptes de démonstration (@demo.vazimba.io).'

    def add_arguments(self, parser):
        parser.add_argument('count', nargs='?', type=int, default=0, help='Nombre de comptes à créer (ou à purger avec --purge)')
        parser.add_argument('--region', default='', help='Forcer une région (slug de regions.py), sinon tirage pondéré')
        parser.add_argument('--purge', action='store_true', help='Supprimer les comptes démo au lieu d\'en créer')
        parser.add_argument('--list', action='store_true', help='Afficher le nombre et quelques comptes démo')

    def handle(self, *args, **opts):
        User = get_user_model()
        demo = User.objects.filter(email__iendswith='@' + DEMO_DOMAIN).order_by('date_joined')

        if opts['list']:
            self.stdout.write(f'{demo.count()} compte(s) démo')
            for u in demo[:20]:
                self.stdout.write(f'  {u.username:<22} {u.email:<40} {u.region}')
            return

        if opts['purge']:
            n = opts['count'] or demo.count()
            ids = list(demo.values_list('pk', flat=True)[:n])
            deleted, _ = User.objects.filter(pk__in=ids).delete()
            self.stdout.write(self.style.SUCCESS(f'{len(ids)} compte(s) démo supprimé(s) (objets liés : {deleted}).'))
            return

        count = opts['count']
        if count <= 0:
            self.stderr.write('Indiquez un nombre de comptes à créer, ex : seed_demo_accounts 500')
            return

        regions = list(VILLES.keys())
        weights = [40, 8, 10, 7, 6, 6, 6, 4, 6, 3]   # Analamanga largement en tête
        created, attempts = 0, 0
        while created < count and attempts < count * 5:
            attempts += 1
            prenom, nom = random.choice(PRENOMS), random.choice(NOMS)
            base = f'{prenom}{nom}'.lower().replace(' ', '')
            username = f'{base}{random.randint(1, 9999)}'[:30]
            email = f'{username}@{DEMO_DOMAIN}'
            region = opts['region'] or random.choices(regions, weights=weights, k=1)[0]
            try:
                with transaction.atomic():
                    u = User(email=email, username=username, region=region,
                             location=random.choice(VILLES.get(region, ['Madagascar'])),
                             bio=random.choice(BIOS), cgu_accepted_at=timezone.now())
                    u.set_unusable_password()
                    u.save()
                created += 1
            except IntegrityError:
                continue
        self.stdout.write(self.style.SUCCESS(f'{created} compte(s) démo créé(s) sur {count} demandé(s). Total démo : {demo.count()}'))
