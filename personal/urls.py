from django.urls import path
from django.views.generic import RedirectView

from .views import home_screen_view

# ─────────────────────────────────────────────────────────────────────────────
# Ces routes déclaraient name='landing' et name='privacy-policy', noms déjà
# utilisés par ZOOT/urls.py pour '/' et '/privacy/'. `personal.urls` étant
# inclus après, c'est lui qui l'emportait au reverse : {% url 'landing' %}
# renvoyait /personal/landing/ dans TOUTE l'application (logo de la barre de
# navigation compris), et la même page était servie sous deux adresses
# distinctes — contenu dupliqué du point de vue des moteurs de recherche.
#
# Les chemins sont conservés en redirection permanente pour ne pas casser les
# liens déjà partagés, mais ils ne portent plus de nom : les noms canoniques
# restent ceux de ZOOT/urls.py.
# ─────────────────────────────────────────────────────────────────────────────

urlpatterns = [
	path('home/', home_screen_view, name='home'),
	path('landing/', RedirectView.as_view(pattern_name='landing', permanent=True)),
	path('privacy/', RedirectView.as_view(pattern_name='privacy-policy', permanent=True)),
]
