"""
Filtres partagés par tout le site (chargés comme « builtins », pas de {% load %}).

`vz_since` : date relative compacte, comme sur les réseaux modernes
    à l'instant · 5 min · 3 h · 2 j · 8 nov. · 8 nov. 2025
Rend un <time datetime="ISO" title="date complète"> que vz-core.js rafraîchit
toutes les minutes (data-vz-since) sans recharger la page.

`vz_ariary` : prix en Ariary avec séparateur de milliers (12 500 Ar).
"""
from datetime import date, datetime, time as dtime

from django import template
from django.utils import timezone, formats
from django.utils.html import format_html
from django.utils.translation import gettext as _

register = template.Library()


def _to_datetime(value):
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, dtime.min)
    else:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_default_timezone())
    return dt


def relative_label(value, now=None):
    """Libellé court et traduit ; chaîne vide si la valeur n'est pas une date."""
    dt = _to_datetime(value)
    if dt is None:
        return ''
    now = now or timezone.now()
    seconds = int((now - dt).total_seconds())
    if seconds < 45:
        return _("à l'instant")
    minutes = seconds // 60
    if minutes < 60:
        return _('%(n)d min') % {'n': max(minutes, 1)}
    hours = minutes // 60
    if hours < 24:
        return _('%(n)d h') % {'n': hours}
    days = hours // 24
    if days < 7:
        return _('%(n)d j') % {'n': days}
    local = timezone.localtime(dt)
    if local.year == timezone.localtime(now).year:
        return formats.date_format(local, 'j b')
    return formats.date_format(local, 'j b Y')


@register.filter(name='vz_since')
def vz_since(value):
    """<time> relatif, rafraîchi côté client. Usage : {{ post.created_at|vz_since }}."""
    dt = _to_datetime(value)
    if dt is None:
        return ''
    local = timezone.localtime(dt)
    return format_html(
        '<time class="vz-time" datetime="{}" data-vz-since title="{}">{}</time>',
        local.isoformat(timespec='seconds'),
        formats.date_format(local, 'DATETIME_FORMAT'),
        relative_label(dt),
    )


@register.filter(name='vz_since_text')
def vz_since_text(value):
    """Variante texte brut (attributs, JSON)."""
    return relative_label(value)


@register.filter(name='vz_ariary')
def vz_ariary(value):
    """12500 → « 12 500 Ar » (espace insécable fine comme séparateur)."""
    try:
        amount = int(round(float(value)))
    except (TypeError, ValueError):
        return ''
    return f"{amount:,}".replace(',', ' ') + ' Ar'


@register.filter(name='vz_notif_verb')
def vz_notif_verb(value):
    """Libellé de notification dans la langue active (voir notification/verbs.py)."""
    from notification.verbs import localize_verb
    return localize_verb(value)


@register.filter(name='vz_group_icon')
def vz_group_icon(category):
    """Nom de Material Icon d'une catégorie de groupe (remplace l'emoji du libellé)."""
    from group.models import Group
    return Group.CATEGORY_ICONS.get(category, 'forum')

