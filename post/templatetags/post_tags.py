"""
Filtres de template pour l'app post.

`safe_html` remplace `|safe` sur tout contenu écrit par un utilisateur
(corps des posts CKEditor, etc.). `|safe` désactivait complètement
l'échappement Django : n'importe quel utilisateur pouvait publier
`<img src=x onerror=...>` et le script s'exécutait chez tous les lecteurs
(XSS stocké → prise de contrôle de compte).

On assainit au rendu plutôt qu'à l'enregistrement pour que le contenu
déjà présent en base soit lui aussi protégé, sans migration de données.
"""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

# Balises autorisées : le sous-ensemble réellement produit par CKEditor
# pour de la mise en forme de texte. Aucune balise capable d'exécuter du
# script ou de charger une ressource active (script, iframe, object, form…).
ALLOWED_TAGS = [
    'p', 'br', 'hr', 'div', 'span',
    'b', 'strong', 'i', 'em', 'u', 's', 'strike', 'sub', 'sup', 'mark',
    'ul', 'ol', 'li', 'blockquote', 'pre', 'code',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'a', 'img',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
]

# `style` est volontairement absent : bleach ne nettoie pas le CSS sans
# css_sanitizer, et une déclaration CSS peut servir à masquer ou déplacer des
# éléments par-dessus l'interface (détournement de clic).
ALLOWED_ATTRIBUTES = {
    '*':   ['class', 'dir'],
    'a':   ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'td':  ['colspan', 'rowspan'],
    'th':  ['colspan', 'rowspan'],
}

# Schémas d'URL autorisés — exclut javascript: et data: (vecteurs XSS)
ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']


@register.filter(name='safe_html')
def safe_html(value):
    """Rend du HTML utilisateur après assainissement (remplace `|safe`)."""
    if not value:
        return ''
    try:
        import bleach
    except ImportError:
        # Sans bleach, on échappe tout plutôt que de laisser passer du script.
        from django.utils.html import escape
        return escape(value)

    cleaned = bleach.clean(
        str(value),
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )
    return mark_safe(cleaned)
