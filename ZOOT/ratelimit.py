"""
Limitation de débit (anti force brute, anti spam).

Fenêtre fixe stockée dans le cache Django : Redis en production quand
REDIS_URL est défini (partagé entre workers), mémoire locale sinon.

Usage, de préférence dans les urls.py pour ne pas toucher aux vues :

    path('login/', ratelimit('10/5m', key='ip')(login_view), name='login'),
"""
import functools
import time

from django.core.cache import cache
from django.http import HttpResponse, JsonResponse

_PERIODS = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}


def _parse_rate(rate):
    """'10/5m' → (10, 300) ; '20/m' → (20, 60)."""
    count, period = rate.split('/')
    unit = period[-1]
    multiplier = int(period[:-1] or 1)
    return int(count), multiplier * _PERIODS[unit]


def client_ip(request):
    """IP du client derrière le proxy Railway.

    Le proxy ajoute l'IP réelle en dernier dans X-Forwarded-For ; les valeurs
    plus à gauche peuvent être forgées par le client.
    """
    real_ip = request.META.get('HTTP_X_REAL_IP')
    if real_ip:
        return real_ip.strip()
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[-1].strip()
    return request.META.get('REMOTE_ADDR', '')


def _too_many(request):
    message = "Trop de tentatives. Réessayez dans quelques minutes."
    wants_json = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
        or request.content_type == 'application/json'
    )
    if wants_json:
        return JsonResponse({'ok': False, 'error': message}, status=429)
    return HttpResponse(message, status=429, content_type='text/plain; charset=utf-8')


def ratelimit(rate, key='user', methods=('POST',)):
    """Limite une vue à `rate` requêtes par client.

    key='user' : par utilisateur connecté (IP pour les anonymes) ;
    key='ip'   : par adresse IP.
    Seules les méthodes listées dans `methods` sont comptées.
    """
    limit, window = _parse_rate(rate)

    def decorator(view):
        scope = f"{view.__module__}.{getattr(view, '__name__', 'view')}"

        @functools.wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method not in methods:
                return view(request, *args, **kwargs)
            user = getattr(request, 'user', None)
            if key == 'user' and user is not None and user.is_authenticated:
                ident = f"u{user.pk}"
            else:
                ident = f"ip{client_ip(request)}"
            bucket = int(time.time() // window)
            cache_key = f"rl:{scope}:{ident}:{bucket}"
            # add() n'écrase pas une clé existante : il initialise la fenêtre.
            cache.add(cache_key, 0, timeout=window)
            try:
                hits = cache.incr(cache_key)
            except ValueError:
                # Clé expirée entre add() et incr() : nouvelle fenêtre.
                cache.set(cache_key, 1, timeout=window)
                hits = 1
            if hits > limit:
                return _too_many(request)
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
