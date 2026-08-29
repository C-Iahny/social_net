import re

from django import template
from django.db.models import Q
from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe
from personal.models import Announcement

register = template.Library()


# Un mot encadré d'astérisques dans le titre du Hero : *malagasy*
_ACCENT = re.compile(r'\*([^*]+)\*')


@register.filter(name='hero_accent')
def hero_accent(value):
    """Met en valeur les portions encadrées d'astérisques du titre du Hero.

    Le titre reste modifiable depuis l'admin, tout en gardant l'accent
    typographique de la maquette : `qui parle *malagasy*.` rend « malagasy »
    dans le serif italique de la charte.

    Le texte est échappé AVANT toute insertion de balise : la valeur vient de
    l'admin, elle ne doit jamais pouvoir injecter du HTML.
    """
    if not value:
        return ''

    texte = escape(str(value))

    def remplacer(m):
        return (
            '<span style="font-family:\'Instrument Serif\',Georgia,serif;'
            'font-weight:400;font-style:italic;letter-spacing:-1.5px;'
            'color:var(--lp-accent);">' + m.group(1) + '</span>'
        )

    # Les sauts de ligne saisis dans l'admin restent des sauts de ligne.
    return mark_safe(_ACCENT.sub(remplacer, texte).replace('\n', '<br>'))


@register.simple_tag
def get_active_announcements(count=5):
    """Retourne les annonces actives et dans leur période de diffusion."""
    now = timezone.now()
    return (
        Announcement.objects
        .filter(is_active=True, start_date__lte=now)
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=now))
        .order_by('-start_date')[:count]
    )
