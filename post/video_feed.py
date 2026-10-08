"""
Fil vidéo vertical (« Vidéos ») : les posts contenant une vidéo, classés
« Pour toi » plutôt que par simple ordre chronologique.

Score d'un post = (1 + 3·réactions + 2·commentaires) × bonus / (âge_jours + 1,5)^1,2
  bonus ×1,5 si l'auteur est un ami, ×1,3 si le post vient de la région de
  l'utilisateur. Les candidats sont les 300 vidéos visibles les plus récentes ;
  le classement est mis en cache 2 minutes par utilisateur pour que le
  défilement (pagination par offset) reste stable.
"""
import html
import json
import logging

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django.views.decorators.http import require_GET

from regions import REGION_LABELS
from .models import Post, PostMedia, Reaction, Comment
from .products import attach_products
from .visibility import visible_posts

logger = logging.getLogger(__name__)

CANDIDATES = 300
PAGE_SIZE = 6
RANK_TTL = 120  # secondes


def _friend_ids(user):
    if not user.is_authenticated:
        return set()
    from friend.models import FriendList
    try:
        return set(FriendList.objects.get(user=user).friends.values_list('id', flat=True))
    except FriendList.DoesNotExist:
        return set()


def ranked_video_post_ids(user):
    """Liste ordonnée des IDs de posts vidéo pour `user` (mise en cache)."""
    key = f"vf:rank:{user.pk if user.is_authenticated else 'anon'}"
    ids = cache.get(key)
    if ids is not None:
        return ids

    posts = list(
        visible_posts(Post.objects.filter(media_files__media_type=PostMedia.VIDEO), user)
        .distinct().order_by('-id')[:CANDIDATES]
    )
    post_ids = [p.id for p in posts]
    reactions = dict(Reaction.objects.filter(post_id__in=post_ids)
                     .values_list('post_id').annotate(c=Count('id')).values_list('post_id', 'c'))
    comments = dict(Comment.objects.filter(post_id__in=post_ids)
                    .values_list('post_id').annotate(c=Count('id')).values_list('post_id', 'c'))
    friends = _friend_ids(user)
    my_region = getattr(user, 'region', '') or ''
    today = timezone.localdate()

    def score(p):
        age_days = max((today - p.post_date).days, 0)
        engagement = 1 + 3 * reactions.get(p.id, 0) + 2 * comments.get(p.id, 0)
        bonus = 1.0
        if p.author_id in friends:
            bonus *= 1.5
        if my_region and p.region == my_region:
            bonus *= 1.3
        return engagement * bonus / ((age_days + 1.5) ** 1.2)

    posts.sort(key=lambda p: (-score(p), -p.id))
    ids = [p.id for p in posts]
    cache.set(key, ids, RANK_TTL)
    return ids


def _caption(body):
    text = html.unescape(strip_tags(body or '')).strip()
    return text if len(text) <= 220 else text[:217].rstrip() + '…'


def _avatar(account):
    try:
        return account.profile_image.url
    except Exception:
        return '/static/images/default_profile_image.png'


def video_page(user, offset, limit=PAGE_SIZE):
    """Retourne (items, next_offset) ; next_offset vaut None en fin de liste."""
    ids = ranked_video_post_ids(user)
    page_ids = ids[offset:offset + limit]
    if not page_ids:
        return [], None

    posts = {p.id: p for p in Post.objects.filter(id__in=page_ids).select_related('author')}
    attach_products(posts.values())
    media_by_post = {}
    for m in PostMedia.objects.filter(post_id__in=page_ids, media_type=PostMedia.VIDEO).order_by('order'):
        media_by_post.setdefault(m.post_id, m)
    reactions = dict(Reaction.objects.filter(post_id__in=page_ids)
                     .values_list('post_id').annotate(c=Count('id')).values_list('post_id', 'c'))
    comments = dict(Comment.objects.filter(post_id__in=page_ids)
                    .values_list('post_id').annotate(c=Count('id')).values_list('post_id', 'c'))
    mine = {}
    if user.is_authenticated:
        mine = dict(Reaction.objects.filter(post_id__in=page_ids, user=user)
                    .values_list('post_id', 'reaction_type'))

    items = []
    for pid in page_ids:
        post, media = posts.get(pid), media_by_post.get(pid)
        if not post or not media or not media.url:
            continue
        poster = None
        if media.poster:
            try:
                poster = media.poster.url
            except Exception:
                poster = None
        items.append({
            'id':            post.id,
            'video':         media.url,
            'poster':        poster,
            'caption':       _caption(post.body),
            'region':        REGION_LABELS.get(post.region, '') if post.region else '',
            'author':        {'id': post.author_id, 'username': post.author.username, 'avatar': _avatar(post.author)},
            'reactions':     reactions.get(pid, 0),
            'comments':      comments.get(pid, 0),
            'user_reaction': mine.get(pid),
            'url':           reverse('post:post-detail', args=[post.id]),
            'is_mine':       post.author_id == getattr(user, 'pk', None),
            'product':       post.product,
        })
    next_offset = offset + limit if offset + limit < len(ids) else None
    return items, next_offset


@login_required(login_url='login')
def video_feed_view(request):
    """Page plein écran du fil vidéo."""
    items, next_offset = video_page(request.user, 0)
    return render(request, 'post/video_feed.html', {
        'initial_items': items,
        'next_offset': next_offset,
    })


@login_required(login_url='login')
@require_GET
def video_feed_more(request):
    """JSON : page suivante du fil vidéo (?offset=N)."""
    try:
        offset = max(int(request.GET.get('offset', 0)), 0)
    except (TypeError, ValueError):
        offset = 0
    items, next_offset = video_page(request.user, offset)
    return JsonResponse({'items': items, 'next_offset': next_offset})
