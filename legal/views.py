from django.shortcuts import render
from django.utils.translation import get_language


def _get_lang(request):
    lang = get_language() or 'fr'
    if lang.startswith('en'):
        return 'en'
    if lang.startswith('mg'):
        return 'mg'
    return 'fr'


def cgu_view(request):
    lang = _get_lang(request)
    templates = {
        'fr': 'legal/cgu_fr.html',
        'en': 'legal/cgu_en.html',
        'mg': 'legal/cgu_mg.html',
    }
    return render(request, templates[lang])


def confidentialite_view(request):
    lang = _get_lang(request)
    templates = {
        'fr': 'legal/confidentialite_fr.html',
        'en': 'legal/confidentialite_en.html',
        'mg': 'legal/confidentialite_mg.html',
    }
    return render(request, templates[lang])
