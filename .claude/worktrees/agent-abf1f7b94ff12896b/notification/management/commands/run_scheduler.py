"""
Management command : run_scheduler
Lance un processus bloquant APScheduler qui exécute les tâches périodiques.

Utilisation (Procfile) :
    worker: python manage.py run_scheduler

Railway : ajouter ce worker comme service séparé dans le dashboard
          OU via Procfile si le plan le permet.

Tâches planifiées :
    - send_daily_digest  : tous les jours à 08h00 (heure serveur = UTC)
"""

import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


def _run_daily_digest():
    """Wrapper appelé par le scheduler — importe Django tard pour éviter les cycles."""
    try:
        from django.core.management import call_command
        logger.info("[scheduler] Lancement du digest quotidien…")
        call_command("send_daily_digest")
        logger.info("[scheduler] Digest terminé.")
    except Exception as exc:
        logger.exception("[scheduler] Erreur lors du digest : %s", exc)


class Command(BaseCommand):
    help = "Démarre le scheduler APScheduler (tâches périodiques)."

    def handle(self, *args, **options):
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = BlockingScheduler(timezone="UTC")

        # ── Digest quotidien à 08h00 UTC ─────────────────────────────────────
        scheduler.add_job(
            _run_daily_digest,
            trigger=CronTrigger(hour=8, minute=0),
            id="daily_digest",
            name="Digest Push Quotidien",
            replace_existing=True,
        )

        self.stdout.write(self.style.SUCCESS(
            "Scheduler démarré — digest à 08h00 UTC chaque jour."
        ))
        logger.info("[scheduler] Démarré.")

        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.stdout.write("Scheduler arrêté.")
            logger.info("[scheduler] Arrêté.")
