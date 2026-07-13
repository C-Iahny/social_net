"""
Middleware personnalisé pour Vazimba / Zoot.
"""

from django.utils import translation
from django.conf import settings


class DefaultFrenchMiddleware:
    """
    Force le français comme langue par défaut pour tout visiteur
    qui n'a pas encore de cookie de langue (zoot_language).

    Fonctionnement :
    - Si le cookie LANGUAGE_COOKIE_NAME n'existe pas → active 'fr' pour cette requête
      et pose le cookie sur la réponse, de sorte que les prochaines visites
      sont déjà en français dès la lecture du cookie par LocaleMiddleware.
    - Si le cookie existe (choix explicite de l'utilisateur : fr / en / mg)
      → ne touche à rien, respect du choix.

    Placement : doit être listé APRÈS LocaleMiddleware dans settings.MIDDLEWARE,
    de façon à s'exécuter après lui dans la phase "requête" et à pouvoir
    écraser la langue qu'il a activée via Accept-Language.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cookie_name = getattr(settings, 'LANGUAGE_COOKIE_NAME', 'django_language')
        force_french = cookie_name not in request.COOKIES

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
