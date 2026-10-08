"""
Onglet « Pour toi » du fil principal : recommandation au-delà du cercle d'amis.

Même recette que le fil vidéo (post/video_feed.py) appliquée à tous les posts
visibles : engagement pondéré par la fraîcheur, bonus amis / abonnements /
région / média / produit à vendre. Le classement est mis en cache deux minutes
par utilisateur, puis paginé comme un fil classique.
"""

from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count
from django.utils import timezone

from .models import Post, PostMedia, Reaction, Comment, Follow
from .visibility import visible_posts

CANDIDATES = 400
RANK_TTL = 120


def _friend_ids(user):
    from friend.models import FriendList
    try:
        return set(FriendList.objects.get(user=user).friends.values_list('id', flat=True))
    except FriendList.DoesNotExist:
        return set()


def ranked_feed_post_ids(user):
    """IDs des posts recommandés pour `user`, du plus pertinent au moins pertinent."""
    key = f'ff:rank:{user.pk}'
    ids = cache.get(key)
    if ids is not None:
        return ids

    posts = list(
        visible_posts(Post.objects.filter(status=Post.STATUS_PUBLISHED).exclude(author=user), user)
        .only('id', 'author_id', 'region', 'post_date', 'annonce_id', 'menu_item_id')
        .order_by('-id')[:CANDIDATES]
    )
    post_ids = [p.id for p in posts]
    reactions = dict(Reaction.objects.filter(post_id__in=post_ids)
                     .values_list('post_id').annotate(c=Count('id')).values_list('post_id', 'c'))
    comments = dict(Comment.objects.filter(post_id__in=post_ids)
                    .values_list('post_id').annotate(c=Count('id')).values_list('post_id', 'c'))
    with_media = set(PostMedia.objects.filter(post_id__in=post_ids).values_list('post_id', flat=True))
    friends = _friend_ids(user)
    followed = set(Follow.objects.filter(user_follower=user).values_list('user_id', flat=True))
    my_region = getattr(user, 'region', '') or ''
    today = timezone.localdate()

    def score(p):
        age_days = max((today - p.post_date).days, 0)
        engagement = 1 + 3 * reactions.get(p.id, 0) + 2 * comments.get(p.id, 0)
        bonus = 1.0
        if p.author_id in friends:
            bonus *= 1.5
        if p.author_id in followed:
            bonus *= 1.3
        if my_region and p.region == my_region:
            bonus *= 1.3
        if p.id in with_media:
            bonus *= 1.2
        if p.annonce_id or p.menu_item_id:
            bonus *= 1.1
        return engagement * bonus / ((age_days + 1.5) ** 1.2)

    posts.sort(key=lambda p: (-score(p), -p.id))
    ids = [p.id for p in posts]
    cache.set(key, ids, RANK_TTL)
    return ids


def foryou_page(user, page_number, per_page=5):
    """Page Django (has_next, next_page_number…) dont object_list est la liste de posts ordonnée."""
    ids = ranked_feed_post_ids(user)
    page = Paginator(ids, per_page).get_page(page_number)
    page_ids = list(page.object_list)
    by_id = {p.id: p for p in Post.objects.filter(id__in=page_ids).select_related('author', 'group')}
    page.object_list = [by_id[i] for i in page_ids if i in by_id]
    return page
