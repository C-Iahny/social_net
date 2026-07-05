"""
Management command : send_daily_digest
Envoie une notification push résumée aux utilisateurs passifs :
  "3 nouvelles publications dans [Antananarivo]" ou
  "Quelqu'un a répondu à votre commentaire"

Utilisation :
  python manage.py send_daily_digest
  python manage.py send_daily_digest --hours 6
  python manage.py send_daily_digest --dry-run

Railway cron : 0 8 * * *  (08h00 chaque matin, heure du serveur)
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Envoie un digest push aux utilisateurs inactifs depuis N heures."

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=3,
            help="Ne notifie que les utilisateurs inactifs depuis au moins N heures (défaut: 3).",
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Simule l'envoi sans rien envoyer réellement.",
        )

    def handle(self, *args, **options):
        from django.db.models import Count, Q

        from account.models import Account
        from bazar.models import Annonce
        from notification.models import PushSubscription
        from post.models import Post

        hours_inactive = options['hours']
        dry_run        = options['dry_run']
        now            = timezone.now()
        inactive_since = now - timedelta(hours=hours_inactive)
        yesterday      = now - timedelta(hours=24)

        if dry_run:
            self.stdout.write(self.style.WARNING("[DRY-RUN] Aucune notification ne sera envoyée."))

        # ── 1. Candidats : utilisateurs ayant au moins une PushSubscription
        #        et n'ayant pas visité depuis hours_inactive heures ──────────
        push_user_ids = PushSubscription.objects.values_list('user_id', flat=True).distinct()

        candidates = Account.objects.filter(
            id__in=push_user_ids,
            last_login__lt=inactive_since,   # pas connecté récemment
        ).prefetch_related('joined_groups')

        self.stdout.write(f"Candidats inactifs depuis >{hours_inactive}h : {candidates.count()}")

        sent = 0
        skipped = 0

        for user in candidates:
            # ── 2a. Posts dans les groupes de l'utilisateur (dernières 24h) ─
            user_groups = list(user.joined_groups.values_list('id', flat=True))
            group_posts = 0
            top_group_name = None

            if user_groups:
                # On compte par groupe pour trouver celui le plus actif
                group_counts = (
                    Post.objects.filter(
                        group_id__in=user_groups,
                        post_date__gte=yesterday.date(),
                    )
                    .values('group__name')
                    .annotate(n=Count('id'))
                    .order_by('-n')
                )
                group_posts = sum(row['n'] for row in group_counts)
                if group_counts:
                    top_group_name = group_counts[0]['group__name']

            # ── 2b. Annonces bazar dans la région de l'utilisateur (24h) ────
            bazar_count = 0
            if user.region:
                bazar_count = Annonce.objects.filter(
                    region=user.region,
                    created_at__gte=yesterday,
                    status='active',
                ).count()

            # ── 2c. Pas de nouveauté → passer ──────────────────────────────
            if group_posts == 0 and bazar_count == 0:
                skipped += 1
                continue

            # ── 3. Composer le message ──────────────────────────────────────
            parts = []
            if group_posts and top_group_name:
                label = (
                    f"{group_posts} publication{'s' if group_posts > 1 else ''} "
                    f"dans {top_group_name}"
                )
                parts.append(label)
            elif group_posts:
                parts.append(
                    f"{group_posts} publication{'s' if group_posts > 1 else ''} "
                    f"dans vos groupes"
                )

            if bazar_count:
                parts.append(
                    f"{bazar_count} annonce{'s' if bazar_count > 1 else ''} "
                    f"dans votre région"
                )

            body = " · ".join(parts)
            title = "VAZIMBA — Ce que vous avez manqué"

            # ── 4. Envoyer ──────────────────────────────────────────────────
            if dry_run:
                self.stdout.write(
                    f"  [DRY] {user.username}: {body}"
                )
                sent += 1
                continue

            try:
                PushSubscription.send_notification(
                    user=user,
                    title=title,
                    body=body,
                    url='/feed/',
                )
                sent += 1
                self.stdout.write(f"  ✓ {user.username}: {body}")
            except Exception as exc:
                self.stderr.write(f"  ✗ {user.username}: {exc}")

        # ── Résumé ──────────────────────────────────────────────────────────
        status_fn = self.style.SUCCESS if not dry_run else self.style.WARNING
        self.stdout.write(
            status_fn(
                f"Digest terminé — envoyés: {sent}, skipped: {skipped}, "
                f"total candidats: {candidates.count()}"
            )
        )
