"""
Middleware personnalisé pour Vazimba / Zoot.
"""

from django.utils import translation
from django.conf import settings


class DefaultFrenchMiddleware:
    """
    Force le français comme langue par défaut pour tout visiteur.

    Fonctionnement :
    - Si le cookie LANGUAGE_COOKIE_NAME n'existe PAS → active 'fr' et pose le cookie.
    - Si le cookie vaut 'en' → l'ancien système géo-IP posait 'en' par défaut pour
      tous les visiteurs non reconnus. On réinitialise à 'fr' car Vazimba est
      un réseau francophone malgache. L'utilisateur peut ensuite choisir EN via le
      sélecteur de langue (ce choix restera mémorisé indéfiniment).
    - Si le cookie vaut 'fr' ou 'mg' (choix délibéré) → on ne touche à rien.

    Placement : doit être listé APRÈS LocaleMiddleware dans settings.MIDDLEWARE,
    de façon à s'exécuter après lui dans la phase "requête" et à pouvoir
    écraser la langue qu'il a activée via Accept-Language.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cookie_name = getattr(settings, 'LANGUAGE_COOKIE_NAME', 'django_language')
        current_lang = request.COOKIES.get(cookie_name)

        # Forcer le français si : pas de cookie, OU cookie='en' auto-posé
        # par l'ancien système géo-IP (qui defaultait à 'en' pour tous).
        # 'fr' et 'mg' sont des choix intentionnels → on les respecte.
        force_french = not current_lang or current_lang == 'en'

        if force_french:
            translation.activate('fr')

        response = self.get_response(request)

        if force_french:
            response.set_cookie(
                cookie_name,
                'fr',
                max_age=getattr(settings, 'LANGUAGE_COOKIE_AGE', 365 * 24 * 3600),
                path=getattr(settings, 'LANGUAGE_COOKIE_PATH', '/'),
                domain=getattr(settings, 'LANGUAGE_COOKIE_DOMAIN', None),
                secure=getattr(settings, 'LANGUAGE_COOKIE_SECURE', False),
                httponly=getattr(settings, 'LANGUAGE_COOKIE_HTTPONLY', False),
                samesite=getattr(settings, 'LANGUAGE_COOKIE_SAMESITE', 'Lax'),
            )

        return response
