"""Chargement groupé et borné des commentaires d'une page de posts."""
from django.db.models import Count


def load_comments_grouped(post_ids, cap=150):
    """Retourne (top_by_post, totals).

    Les `cap` commentaires les plus récents de la page (toutes publications
    confondues) sont chargés en une requête, puis groupés : un post viral à
    plusieurs milliers de commentaires n'alourdit plus chaque affichage du
    fil ou du profil. `totals` donne le vrai nombre par post (COUNT groupé).
    Les réponses dont le parent n'est pas dans la fenêtre sont ignorées.
    """
    from .models import Comment
    post_ids = list(post_ids)
    if not post_ids:
        return {}, {}
    totals = dict(
        Comment.objects.filter(post_id__in=post_ids)
        .values_list('post_id').annotate(n=Count('id')).values_list('post_id', 'n')
    )
    newest = list(
        Comment.objects.filter(post_id__in=post_ids)
        .select_related('author').order_by('-created_at', '-id')[:cap]
    )
    newest.reverse()                     # ordre chronologique pour l'affichage
    top_by_post, replies_map = {}, {}
    for c in newest:
        if c.parent_id is None:
            top_by_post.setdefault(c.post_id, []).append(c)
        else:
            replies_map.setdefault(c.parent_id, []).append(c)
    for comments in top_by_post.values():
        for c in comments:
            c.reply_list = replies_map.get(c.id, [])
    return top_by_post, totals
