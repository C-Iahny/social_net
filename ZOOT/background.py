"""
Exécution de petites tâches en arrière-plan, hors de la requête HTTP.

Le projet n'a pas de file de tâches (Celery, RQ…). Pour les travaux courts
qui ne doivent pas faire attendre l'utilisateur — envoi de notifications
push, recompression d'une vidéo — un pool de threads suffit : il tourne dans
le même process que Daphne et se vide proprement à l'arrêt.

Chaque tâche ferme ses connexions de base de données (close_old_connections)
pour ne pas en laisser traîner d'un thread à l'autre.
"""
import logging
from concurrent.futures import ThreadPoolExecutor

from django.db import close_old_connections

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='zoot-bg')


def _wrap(fn, args, kwargs):
    close_old_connections()
    try:
        fn(*args, **kwargs)
    except Exception:
        logger.exception("Tâche de fond %s en erreur", getattr(fn, '__name__', fn))
    finally:
        close_old_connections()


def run_in_background(fn, *args, **kwargs):
    """Planifie fn(*args, **kwargs) dans le pool et rend la main immédiatement."""
    return _executor.submit(_wrap, fn, args, kwargs)
