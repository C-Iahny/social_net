"""
Libellés de notification traduits à l'affichage.

Les notifications d'amitié (friend/models.py) stockent depuis l'origine un
verbe anglais en base (« X sent you a friend request. »). Plutôt que de
migrer les lignes existantes, on reconnaît ces motifs au moment de servir la
notification (journal, menu déroulant, WebSocket) et on les rend dans la
langue active. Tout verbe inconnu est renvoyé tel quel.
"""
import re

from django.utils.translation import gettext as _

# (motif anglais, libellé traduisible avec %(name)s)
_PATTERNS = [
    (re.compile(r"^(?P<name>.+?) sent you a friend request\.?$"),
     lambda n: _("%(name)s vous a envoyé une demande d’ami") % {'name': n}),
    (re.compile(r"^You are now friends with (?P<name>.+?)\.?$"),
     lambda n: _("Vous êtes maintenant ami(e) avec %(name)s") % {'name': n}),
    (re.compile(r"^You are no longer friends with (?P<name>.+?)\.?$"),
     lambda n: _("Vous n’êtes plus ami(e) avec %(name)s") % {'name': n}),
    (re.compile(r"^You accepted (?P<name>.+?)'s friend request\.?$"),
     lambda n: _("Vous avez accepté la demande d’ami de %(name)s") % {'name': n}),
    (re.compile(r"^(?P<name>.+?) accepted your friend request\.?$"),
     lambda n: _("%(name)s a accepté votre demande d’ami") % {'name': n}),
    (re.compile(r"^You declined (?P<name>.+?)'s friend request\.?$"),
     lambda n: _("Vous avez refusé la demande d’ami de %(name)s") % {'name': n}),
    (re.compile(r"^(?P<name>.+?) declined your friend request\.?$"),
     lambda n: _("%(name)s a refusé votre demande d’ami") % {'name': n}),
    (re.compile(r"^You cancelled the friend request to (?P<name>.+?)\.?$"),
     lambda n: _("Vous avez annulé votre demande d’ami à %(name)s") % {'name': n}),
    (re.compile(r"^(?P<name>.+?) cancelled the friend request sent to you\.?$"),
     lambda n: _("%(name)s a annulé sa demande d’ami") % {'name': n}),
]


def localize_verb(verb):
    """Rend un verbe de notification dans la langue active ('' si vide)."""
    if not verb:
        return ''
    for pattern, render in _PATTERNS:
        m = pattern.match(verb.strip())
        if m:
            return render(m.group('name'))
    return verb
