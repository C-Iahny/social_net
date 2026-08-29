"""
Filtrage de visibilité des posts.

Deux fuites étaient présentes partout où une liste de posts était construite
(profil, recherche, hashtags, onglet région) :

  1. les brouillons et posts programmés non échus (status draft/scheduled)
     apparaissaient aux autres utilisateurs ;
  2. les posts publiés dans un groupe **privé** étaient visibles hors du
     groupe, alors que la page du groupe elle-même est bien protégée.

`visible_posts()` centralise la règle pour qu'elle ne puisse plus être
oubliée dans une nouvelle vue.
"""
from django.db.models import Q
from django.utils import timezone


def visible_posts(qs, viewer, author=None):
    """Restreint `qs` aux posts que `viewer` a le droit de voir.

    Args:
        qs:     QuerySet de Post.
        viewer: request.user (peut être anonyme).
        author: si fourni et égal à `viewer`, celui-ci voit tous ses propres
                posts (brouillons compris) — utile sur son propre profil.
    """
    if author is not None and getattr(viewer, 'is_authenticated', False) and viewer == author:
        return qs

    now = timezone.now()
    qs = qs.filter(Q(status='published') | Q(status='scheduled', scheduled_at__lte=now))

    from group.models import Group, GroupMembership

    public_or_none = Q(group__isnull=True) | ~Q(group__privacy=Group.PRIVATE)
    if getattr(viewer, 'is_authenticated', False):
        member_group_ids = GroupMembership.objects.filter(user=viewer).values('group_id')
        # L'auteur voit toujours ses propres posts publiés, même en groupe privé.
        qs = qs.filter(public_or_none | Q(group_id__in=member_group_ids) | Q(author=viewer))
    else:
        qs = qs.filter(public_or_none)

    return qs
