from django.shortcuts import render
from django.http import HttpResponse


def service_worker(request):
    """
    Sert /sw.js depuis un template Django (pour pouvoir y injecter des URLs).
    Le Service Worker DOIT être servi depuis la racine pour avoir scope = '/'.
    """
    response = render(request, 'pwa/sw.js', content_type='application/javascript; charset=utf-8')
    # Autoriser le scope '/' même si servi depuis /sw.js
    response['Service-Worker-Allowed'] = '/'
    # Ne JAMAIS mettre en cache le SW lui-même
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    return response


def manifest(request):
    """Sert /manifest.json (requis par les navigateurs pour l'installation PWA)."""
    response = render(request, 'pwa/manifest.json', content_type='application/manifest+json')
    response['Cache-Control'] = 'public, max-age=86400'  # 1 jour
    return response


def offline(request):
    """Page de fallback hors ligne — mise en cache par le SW."""
    return render(request, 'pwa/offline.html')
