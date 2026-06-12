import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import DeleteView, UpdateView, CreateView
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.template.loader import render_to_string
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

_logger = logging.getLogger(__name__)

User = get_user_model()

from account.models import Account
from django.http import JsonResponse
from .forms import PostForm, EditForm, CommentForm
from .models import Post, Repost, Continent, Country, Follow, Comment, Reaction, PostMedia
from friend.models import FriendList
from personal.models import HeroSettings

# Import différé pour éviter les imports circulaires
try:
    from group.models import Group as Group_model
except ImportError:
    Group_model = None


# ──────────────────────────────────────────────────────────────
# Trending hashtags (cached, recalculé toutes les 30 min)
# ──────────────────────────────────────────────────────────────
def get_trending_hashtags(limit=10, days=7):
    """
    Extrait et classe les hashtags les plus utilisés dans les posts récents.
    Résultat mis en cache 30 minutes (LocMemCache).
    """
    import re
    from datetime import timedelta
    from django.utils import timezone
    from django.core.cache import cache

    cache_key = f'trending_hashtags_{limit}_{days}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    cutoff = timezone.now().date() - timedelta(days=days)
    posts = Post.objects.filter(post_date__gte=cutoff).values_list('body', 'title')

    counts = {}
    pattern = re.compile(r'#([a-zA-ZÀ-ÿ0-9_]{2,30})')
    for body, title in posts:
        # Nettoyer les balises HTML avant d'extraire
        text = re.sub(r'<[^>]+>', ' ', (body or '') + ' ' + (title or ''))
        for tag in pattern.findall(text):
            t = tag.lower()
            counts[t] = counts.get(t, 0) + 1

    result = [
        {'tag': '#' + tag, 'count': cnt}
        for tag, cnt in sorted(counts.items(), key=lambda x: -x[1])[:limit]
    ]
    cache.set(cache_key, result, 1800)  # 30 min
    return result


# ──────────────────────────────────────────────
# Index — page Explore publique (feed/index/)
# ──────────────────────────────────────────────
def Index(request):
    from django.db.models import Count

    # ── Tri dynamique ─────────────────────────────────────────────────────────
    # ?sort=popular → classés par nombre de likes
    # ?sort=recent  → classés par date (défaut)
    sort = request.GET.get('sort', 'recent')

    posts_qs = Post.objects.select_related("author")
    if sort == 'popular':
        # annotate évite le N+1 de total_likes() en template
        posts_qs = posts_qs.annotate(like_count=Count('likes', distinct=True)).order_by("-like_count", "-id")
    else:
        posts_qs = posts_qs.order_by("-id")

    recent_posts = posts_qs[:12]

    # ── Sidebar : continents avec compte de pays en une seule requête ─────────
    # FIX N+1 : on annotate au lieu de c.country_set.count dans le template
    continent = Continent.objects.annotate(country_count=Count('country')).order_by('name')
    countries = Country.objects.select_related('continent').order_by('name')

    # ── Stats globales ────────────────────────────────────────────────────────
    total_post_count = Post.objects.count()
    total_user_count = User.objects.count()

    hero = HeroSettings.get()          # singleton — crée l'instance si absente

    context = {
        "continent":        continent,
        "countries":        countries,
        "recent_posts":     recent_posts,
        "hero":             hero,
        "sort":             sort,
        "total_post_count": total_post_count,
        "total_user_count": total_user_count,
    }
    return render(request, "post/index.html", context)


# ──────────────────────────────────────────────
def _attach_media(posts, post_ids):
    """Attache post.media_list à chaque post (liste de PostMedia). Silencieux si table absente."""
    try:
        media_qs = PostMedia.objects.filter(post_id__in=post_ids).order_by('order')
        media_map = {}
        for m in media_qs:
            media_map.setdefault(m.post_id, []).append(m)
        for post in posts:
            post.media_list = media_map.get(post.id, [])
    except Exception:
        for post in posts:
            post.media_list = []




def _attach_reposts(posts, post_ids, user):
    """Attache post.repost_count et post.user_reposted à chaque post."""
    try:
        from django.db.models import Count
        counts_qs = Repost.objects.filter(post_id__in=post_ids).values('post_id').annotate(c=Count('id'))
        count_map = {row['post_id']: row['c'] for row in counts_qs}
        user_reposts = set(
            Repost.objects.filter(post_id__in=post_ids, user=user).values_list('post_id', flat=True)
        ) if user.is_authenticated else set()
        for post in posts:
            post.repost_count   = count_map.get(post.id, 0)
            post.user_reposted  = post.id in user_reposts
    except Exception:
        for post in posts:
            post.repost_count  = 0
            post.user_reposted = False

# Feed
# ──────────────────────────────────────────────
@login_required(login_url="login")
def post_feed_view(request):
    """Fil d'actualité : posts de l'utilisateur + ses amis."""
    user = request.user

    # Récupérer la liste d'amis (créer si absente)
    try:
        friend_list = FriendList.objects.get(user=user)
        friends = friend_list.friends.all()
    except FriendList.DoesNotExist:
        friend_list = FriendList(user=user)
        friend_list.save()
        friends = friend_list.friends.none()

    # Posts : les siens + ceux de ses amis
    # select_related évite le N+1 (1 JOIN au lieu de 1 requête par post)
    feed_posts = Post.objects.filter(
        author__in=list(friends) + [user]
    ).select_related('author', 'group').order_by("-id")

    # Pagination (5 posts par page)
    paginator = Paginator(feed_posts, 5)
    page_number = request.GET.get("page")
    posts_of_the_page = paginator.get_page(page_number)

    # Quelques statistiques pour le sidebar
    from post.models import Post as PostModel
    my_post_count = PostModel.objects.filter(author=user).count()

    # Précharger les commentaires pour tous les posts de la page
    post_ids = [p.id for p in posts_of_the_page]
    from .models import Comment as CommentModel
    comments_all = list(CommentModel.objects.filter(
        post_id__in=post_ids
    ).select_related('author').order_by('created_at'))

    # Organiser : commentaires racine par post, réponses par commentaire parent
    top_by_post = {}     # post_id → [top-level Comment]
    replies_map = {}     # parent_comment_id → [Reply Comment]
    for c in comments_all:
        if c.parent_id is None:
            top_by_post.setdefault(c.post_id, []).append(c)
        else:
            replies_map.setdefault(c.parent_id, []).append(c)
    for comments in top_by_post.values():
        for c in comments:
            c.reply_list = replies_map.get(c.id, [])

    # Précharger les réactions
    from .models import Reaction
    from django.db.models import Count
    reactions_qs = (
        Reaction.objects.filter(post_id__in=post_ids)
        .values('post_id', 'reaction_type')
        .annotate(c=Count('id'))
    )
    reactions_by_post = {}
    for row in reactions_qs:
        reactions_by_post.setdefault(row['post_id'], {})[row['reaction_type']] = row['c']

    # Réaction de l'utilisateur courant
    user_reactions_qs = Reaction.objects.filter(
        post_id__in=post_ids, user=user
    ).values_list('post_id', 'reaction_type')
    user_reaction_by_post = {pid: rtype for pid, rtype in user_reactions_qs}

    # Attacher les données directement à chaque post
    for post in posts_of_the_page:
        top = top_by_post.get(post.id, [])
        for c in top:
            if not hasattr(c, 'reply_list'):
                c.reply_list = []
        post.page_comments   = top
        post.total_comments  = len(top) + sum(len(c.reply_list) for c in top)
        post.reaction_counts = reactions_by_post.get(post.id, {})
        post.user_reaction   = user_reaction_by_post.get(post.id)
        post.total_reactions = sum(post.reaction_counts.values())
    _attach_media(posts_of_the_page, post_ids)

    # Groupes de l'utilisateur (raccourci sidebar droite)
    my_groups = []
    if Group_model is not None:
        my_groups = list(
            Group_model.objects.filter(memberships__user=user)
            .select_related('creator')
            .distinct()[:6]
        )

    context = {
        "friends":            friends,
        "friends_count":      friends.count(),
        "posts_of_the_page":  posts_of_the_page,
        "post_form":          PostForm(),
        "my_post_count":      my_post_count,
        "trending_hashtags":  get_trending_hashtags(),
        "my_groups":          my_groups,
    }
    return render(request, "post/post_view.html", context)


# ──────────────────────────────────────────────
# Feed — Infinite Scroll (AJAX fragment)
# ──────────────────────────────────────────────
@login_required(login_url="login")
def post_feed_more(request):
    """Retourne le fragment HTML des posts pour l'infinite scroll."""
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return redirect('post:post-view')

    user = request.user
    try:
        friend_list = FriendList.objects.get(user=user)
        friends = friend_list.friends.all()
    except FriendList.DoesNotExist:
        friends = []

    feed_posts = Post.objects.filter(
        author__in=list(friends) + [user]
    ).select_related('author', 'group').order_by("-id")

    paginator = Paginator(feed_posts, 5)
    page_number = request.GET.get("page", 1)
    posts_page = paginator.get_page(page_number)

    # Précharger les commentaires
    post_ids = [p.id for p in posts_page]
    from .models import Comment as CommentModel
    comments_all = list(CommentModel.objects.filter(
        post_id__in=post_ids
    ).select_related('author').order_by('created_at'))

    top_by_post = {}
    replies_map = {}
    for c in comments_all:
        if c.parent_id is None:
            top_by_post.setdefault(c.post_id, []).append(c)
        else:
            replies_map.setdefault(c.parent_id, []).append(c)
    for comments in top_by_post.values():
        for c in comments:
            c.reply_list = replies_map.get(c.id, [])

    # Précharger les réactions
    from .models import Reaction
    from django.db.models import Count
    reactions_qs = (
        Reaction.objects.filter(post_id__in=post_ids)
        .values('post_id', 'reaction_type')
        .annotate(c=Count('id'))
    )
    reactions_by_post = {}
    for row in reactions_qs:
        reactions_by_post.setdefault(row['post_id'], {})[row['reaction_type']] = row['c']

    user_reactions_qs = Reaction.objects.filter(
        post_id__in=post_ids, user=user
    ).values_list('post_id', 'reaction_type')
    user_reaction_by_post = {pid: rtype for pid, rtype in user_reactions_qs}

    for post in posts_page:
        top = top_by_post.get(post.id, [])
        for c in top:
            if not hasattr(c, 'reply_list'):
                c.reply_list = []
        post.page_comments   = top
        post.total_comments  = len(top) + sum(len(c.reply_list) for c in top)
        post.reaction_counts = reactions_by_post.get(post.id, {})
        post.user_reaction   = user_reaction_by_post.get(post.id)
        post.total_reactions = sum(post.reaction_counts.values())
    _attach_media(posts_page, post_ids)

    html = render_to_string(
        'post/post_cards_fragment.html',
        {'posts_of_the_page': posts_page, 'request': request},
        request=request,
    )

    return JsonResponse({
        'html':      html,
        'has_next':  posts_page.has_next(),
        'next_page': posts_page.next_page_number() if posts_page.has_next() else None,
    })


# ──────────────────────────────────────────────
# Add Post
# ──────────────────────────────────────────────
@method_decorator(login_required(login_url="login"), name="dispatch")
class AddPostView(CreateView):
    model = Post
    form_class = PostForm
    template_name = "post/add_post.html"

    def form_valid(self, form):
        form.instance.author = self.request.user
        response = super().form_valid(form)
        post = self.object

        # ── Enregistrer les fichiers média sur R2 ────────────────────────
        _VIDEO_EXTS = {'mp4', 'webm', 'ogg', 'mov', 'mkv', 'avi', 'm4v', '3gp'}
        files = self.request.FILES.getlist('media_files')
        _logger.info("AddPostView: %d fichier(s) reçu(s) post #%s", len(files), post.pk)
        saved = 0
        for i, f in enumerate(files):
            ext = f.name.rsplit('.', 1)[-1].lower() if '.' in f.name else ''
            is_vid = ext in _VIDEO_EXTS
            mtype = 'video' if is_vid else 'image'
            try:
                PostMedia.objects.create(post=post, file=f, media_type=mtype, order=i)
                saved += 1
            except Exception as e:
                _logger.exception("PostMedia FAILED (fichier=%s): %s", f.name, e)
        if saved:
            messages.success(self.request, f"{saved} média(s) sauvegardé(s).")
        elif files:
            messages.warning(self.request, "Aucun fichier sauvegardé — voir les logs.")

        # Notify each friend via WebSocket channel layer
        author = self.request.user
        try:
            friend_list = FriendList.objects.get(user=author)
            friends = friend_list.friends.all()
        except FriendList.DoesNotExist:
            friends = []

        # Notifier via WebSocket — enveloppé dans try/except :
        # si Redis est indisponible ou channel_layer=None, le post est quand même
        # sauvegardé et l'utilisateur est redirigé normalement (pas de 500).
        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                for friend in friends:
                    async_to_sync(channel_layer.group_send)(
                        f"user_{friend.id}",
                        {
                            "type": "new_post_notification",
                            "from_username": author.username,
                            "from_image":    author.profile_image.url,
                            "post_title":    post.title,
                            "post_id":       post.id,
                        }
                    )
        except Exception:
            pass  # échec WebSocket non bloquant : le post existe déjà en base

        return response

    def get_success_url(self):
        return reverse_lazy("post:post-view")


# ──────────────────────────────────────────────
# Edit Post
# ──────────────────────────────────────────────
@method_decorator(login_required(login_url="login"), name="dispatch")
class UpdatePostView(UpdateView):
    model = Post
    form_class = EditForm
    template_name = "post/update_post.html"

    def dispatch(self, request, *args, **kwargs):
        post = get_object_or_404(Post, pk=kwargs["pk"])
        if post.author != request.user:
            return HttpResponse("Vous ne pouvez pas modifier ce post.", status=403)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            ctx['existing_media'] = list(PostMedia.objects.filter(post=self.object).order_by('order'))
        except Exception:
            ctx['existing_media'] = []
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        post = self.object

        # Supprimer les médias cochés
        delete_ids = self.request.POST.getlist('delete_media')
        if delete_ids:
            try:
                PostMedia.objects.filter(post=post, id__in=delete_ids).delete()
            except Exception as e:
                _logger.error("delete_media failed: %s", e)

        # Ajouter les nouveaux fichiers
        _VIDEO_EXTS = {'mp4', 'webm', 'ogg', 'mov', 'mkv', 'avi', 'm4v', '3gp'}
        files = self.request.FILES.getlist('media_files')
        try:
            start_order = (PostMedia.objects.filter(post=post)
                           .order_by('-order').values_list('order', flat=True).first() or -1) + 1
        except Exception:
            start_order = 0
        for i, f in enumerate(files):
            ext = f.name.rsplit('.', 1)[-1].lower() if '.' in f.name else ''
            is_vid = ext in _VIDEO_EXTS
            mtype = 'video' if is_vid else 'image'
            try:
                PostMedia.objects.create(post=post, file=f, media_type=mtype, order=start_order + i)
            except Exception as e:
                _logger.exception("UpdatePost: PostMedia FAILED (fichier=%s): %s", f.name, e)

        return response

    def get_success_url(self):
        return reverse_lazy("post:post-view")


# ──────────────────────────────────────────────
# Delete Post
# ──────────────────────────────────────────────
@method_decorator(login_required(login_url="login"), name="dispatch")
class DeletePostView(DeleteView):
    model = Post
    template_name = "post/delete_post.html"
    success_url = reverse_lazy("post:post-view")

    def dispatch(self, request, *args, **kwargs):
        post = get_object_or_404(Post, pk=kwargs["pk"])
        if post.author != request.user:
            return HttpResponse("Vous ne pouvez pas supprimer ce post.", status=403)
        return super().dispatch(request, *args, **kwargs)


# ──────────────────────────────────────────────
# Like / Unlike
# ──────────────────────────────────────────────
@login_required(login_url="login")
def like_post(request):
    post_id = request.GET.get("post_id")
    post    = get_object_or_404(Post, id=post_id)

    if post.likes.filter(id=request.user.id).exists():
        post.likes.remove(request.user)
        liked = False
    else:
        post.likes.add(request.user)
        liked = True

    # ── Requête AJAX → JSON (pas de rechargement, pas de scroll to top) ───────
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'liked':       liked,
            'total_likes': post.likes.count(),
        })

    # ── Requête classique (fallback sans JS) → redirection ────────────────────
    next_url = request.GET.get("next") or request.META.get("HTTP_REFERER") or "post:post-view"
    return redirect(next_url)


# ──────────────────────────────────────────────
# Follow / Unfollow
# ──────────────────────────────────────────────
@login_required(login_url="login")
def follow(request):
    if request.method != "POST":
        return redirect("post:post-view")
    userfollow_name = request.POST.get("userfollow", "")
    try:
        current_user = Account.objects.get(pk=request.user.id)
        user_to_follow = Account.objects.get(username=userfollow_name)
        Follow.objects.get_or_create(user=current_user, user_follower=user_to_follow)
        return redirect("account:view", user_id=user_to_follow.id)
    except Account.DoesNotExist:
        return redirect("post:post-view")


@login_required(login_url="login")
def unfollow(request):
    if request.method != "POST":
        return redirect("post:post-view")
    userfollow_name = request.POST.get("userfollow", "")
    try:
        current_user = Account.objects.get(pk=request.user.id)
        user_to_unfollow = Account.objects.get(username=userfollow_name)
        Follow.objects.filter(user=current_user, user_follower=user_to_unfollow).delete()
        return redirect("account:view", user_id=user_to_unfollow.id)
    except Account.DoesNotExist:
        return redirect("post:post-view")


# ──────────────────────────────────────────────
# Comments
# ──────────────────────────────────────────────
@login_required(login_url="login")
def add_comment(request, post_id):
    """Ajoute un commentaire via POST (AJAX ou classique)."""
    post = get_object_or_404(Post, id=post_id)
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée."}, status=405)

    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post   = post
        comment.author = request.user
        # Support threaded replies
        parent_id = request.POST.get('parent_id')
        if parent_id:
            try:
                from .models import Comment as CommentModel
                parent_comment = CommentModel.objects.get(id=int(parent_id), post=post)
                comment.parent = parent_comment
            except (ValueError, CommentModel.DoesNotExist):
                pass
        comment.save()

        # Push notification au propriétaire du post
        if post.author != request.user:
            try:
                from notification.models import PushSubscription
                PushSubscription.send_notification(
                    user  = post.author,
                    title = 'VAZIMBA — Commentaire',
                    body  = f"{request.user.username} a commenté votre post : {comment.body[:60]}",
                    url   = '/feed/',
                )
            except Exception:
                pass

        # Réponse JSON pour AJAX
        return JsonResponse({
            "ok":         True,
            "id":         comment.id,
            "author":     comment.author.username,
            "avatar":     comment.author.profile_image.url,
            "author_id":  comment.author.id,
            "body":       comment.body,
            "created_at": comment.created_at.strftime("%d %b %Y, %H:%M"),
            "can_delete": True,
            "parent_id":  comment.parent_id,
        })

    return JsonResponse({"error": "Commentaire invalide."}, status=400)


@login_required(login_url="login")
def new_comments(request, post_id):
    """
    Retourne les commentaires créés après `since` (ISO timestamp ou comment id).
    GET /post/<id>/comments/new/?since=<comment_id>
    """
    from django.views.decorators.http import require_GET
    post = get_object_or_404(Post, id=post_id)
    since_id = request.GET.get('since', 0)
    try:
        since_id = int(since_id)
    except (ValueError, TypeError):
        since_id = 0

    qs = Comment.objects.filter(post=post, id__gt=since_id, parent__isnull=True).select_related('author').order_by('id')
    comments = []
    for c in qs:
        can_delete = (request.user == c.author or request.user == post.author)
        comments.append({
            "id":        c.id,
            "author":    c.author.username,
            "author_id": c.author.id,
            "avatar":    c.author.profile_image.url,
            "body":      c.body,
            "created_at": c.created_at.strftime("%d %b %Y, %H:%M"),
            "can_delete": can_delete,
            "parent_id": c.parent_id,
        })
    return JsonResponse({"comments": comments})


@login_required(login_url="login")
def delete_comment(request, comment_id):
    """Supprime un commentaire (auteur ou auteur du post uniquement)."""
    comment = get_object_or_404(Comment, id=comment_id)
    if request.user != comment.author and request.user != comment.post.author:
        return JsonResponse({"error": "Non autorisé."}, status=403)
    comment.delete()
    return JsonResponse({"ok": True})


# ──────────────────────────────────────────────
# Reactions
# ──────────────────────────────────────────────
@login_required(login_url="login")
def react_post(request):
    """Ajoute, change ou supprime une réaction (toggle). Retourne JSON."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    post_id       = request.POST.get('post_id')
    reaction_type = request.POST.get('reaction', 'like')
    post          = get_object_or_404(Post, id=post_id)

    VALID = {'like', 'heart', 'laugh', 'wow', 'sad'}
    if reaction_type not in VALID:
        return JsonResponse({'error': 'Invalid reaction'}, status=400)

    try:
        existing = Reaction.objects.get(post=post, user=request.user)
        if existing.reaction_type == reaction_type:
            # Même réaction → suppression (toggle off)
            existing.delete()
            user_reaction = None
        else:
            # Réaction différente → mise à jour
            existing.reaction_type = reaction_type
            existing.save(update_fields=['reaction_type'])
            user_reaction = reaction_type
    except Reaction.DoesNotExist:
        Reaction.objects.create(post=post, user=request.user, reaction_type=reaction_type)
        user_reaction = reaction_type

    # Compte par type
    from django.db.models import Count
    counts_qs = (
        Reaction.objects.filter(post=post)
        .values('reaction_type')
        .annotate(c=Count('id'))
    )
    counts = {row['reaction_type']: row['c'] for row in counts_qs}
    total  = sum(counts.values())

    # Push notification au propriétaire du post (sauf si c'est lui-même qui réagit)
    if user_reaction and post.author != request.user:
        try:
            from notification.models import PushSubscription
            EMOJI = {'like':'👍','heart':'❤️','laugh':'😂','wow':'😮','sad':'😢'}
            PushSubscription.send_notification(
                user  = post.author,
                title = 'VAZIMBA — Réaction',
                body  = f"{request.user.username} a réagi {EMOJI.get(user_reaction,'👍')} à votre post",
                url   = '/feed/',
            )
        except Exception:
            pass

    return JsonResponse({
        'user_reaction': user_reaction,
        'counts':        counts,
        'total':         total,
    })


# ──────────────────────────────────────────────
# Hashtag Search
# ──────────────────────────────────────────────
@login_required(login_url="login")
def hashtag_view(request, tag):
    """Affiche les posts contenant un hashtag donné."""
    from django.db.models import Q
    tag_clean = tag.lstrip('#').lower()
    posts = Post.objects.filter(
        Q(body__icontains='#' + tag_clean) | Q(title__icontains='#' + tag_clean)
    ).select_related('author', 'group').order_by('-id')

    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    posts_page = paginator.get_page(page_number)

    post_ids = [p.id for p in posts_page]
    _attach_media(list(posts_page), post_ids)

    return render(request, 'post/hashtag.html', {
        'tag':   '#' + tag_clean,
        'posts': posts_page,
    })


# ──────────────────────────────────────────────
# Mention autocomplete
# ──────────────────────────────────────────────
@login_required(login_url="login")
def mention_autocomplete(request):
    """Retourne les utilisateurs dont le nom commence par 'q' (pour l'autocomplétion)."""
    q = request.GET.get('q', '').strip()
    if not q:
        return JsonResponse({'users': []})
    users = User.objects.filter(username__istartswith=q).values(
        'id', 'username'
    )[:8]
    result = [
        {'id': u['id'], 'username': u['username']}
        for u in users
    ]
    return JsonResponse({'users': result})




# ──────────────────────────────────────────────
# Repost (toggle)
# ──────────────────────────────────────────────
@login_required(login_url="login")
def repost_post(request):
    """Toggle repost : publie ou annule la republication d'un post."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    post_id = request.POST.get("post_id")
    post = get_object_or_404(Post, id=post_id)

    repost, created = Repost.objects.get_or_create(user=request.user, post=post)
    if not created:
        repost.delete()
        reposted = False
    else:
        reposted = True

    repost_count = post.reposts.count()
    return JsonResponse({"reposted": reposted, "repost_count": repost_count})

@login_required(login_url='login')
def post_detail(request, post_id):
    """Page de détail d'un post — toutes les réactions et tous les commentaires."""
    from django.shortcuts import get_object_or_404
    from django.db.models import Count
    from django.urls import reverse

    post = get_object_or_404(Post.objects.select_related('author'), pk=post_id)

    # Reactions
    reactions_qs = (
        Reaction.objects.filter(post=post)
        .values('reaction_type')
        .annotate(c=Count('id'))
    )
    reaction_counts = {r['reaction_type']: r['c'] for r in reactions_qs}
    user_reaction = None
    if request.user.is_authenticated:
        try:
            user_reaction = Reaction.objects.get(post=post, user=request.user).reaction_type
        except Reaction.DoesNotExist:
            pass

    post.reaction_counts = reaction_counts
    post.total_reactions = sum(reaction_counts.values())
    post.user_reaction = user_reaction

    # Tous les commentaires (threaded)
    all_comments = list(
        Comment.objects.filter(post=post).select_related('author').order_by('created_at')
    )
    top_comments = [c for c in all_comments if c.parent_id is None]
    replies_map = {}
    for c in all_comments:
        if c.parent_id:
            replies_map.setdefault(c.parent_id, []).append(c)
    for c in top_comments:
        c.reply_list = replies_map.get(c.id, [])

    post.page_comments = top_comments
    post.total_comments = len(all_comments)

    # Médias
    _attach_media([post], [post.id])

    return render(request, 'post/post_detail.html', {
        'post': post,
        'comment_url': reverse('post:add-comment', args=[post.id]),
    })


# ── Kabary numérique ──────────────────────────────────────────────────────────

@login_required(login_url='login')
def kabary_create(request):
    """Page de création d'un Kabary numérique."""
    if request.method == 'POST':
        # La page utilise TOUJOURS fetch() — on retourne toujours du JSON pour les POST.
        # Ne pas dépendre de X-Requested-With (peut être supprimé par Cloudflare).

        fisaorana   = request.POST.get('fisaorana', '').strip()
        fanafahana  = request.POST.get('fanafahana', '').strip()
        vato        = request.POST.get('vato', '').strip()
        ohabolana   = request.POST.get('ohabolana', '').strip()
        famaranana  = request.POST.get('famaranana', '').strip()

        if not vato and not fanafahana:
            return JsonResponse({'ok': False, 'error': 'Le contenu principal (Vato misaina) est obligatoire.'})

        # Assembler le body structuré en HTML
        parts = []
        if fisaorana:
            parts.append(
                f'<div class="kbr-fisaorana"><span class="kbr-label">Fisaorana</span>'
                f'<p>{fisaorana}</p></div>'
            )
        if fanafahana:
            parts.append(
                f'<div class="kbr-section"><span class="kbr-label">Fanafahana</span>'
                f'<p>{fanafahana}</p></div>'
            )
        if vato:
            parts.append(
                f'<div class="kbr-section kbr-vato"><span class="kbr-label">Vato misaina</span>'
                f'<p>{vato}</p></div>'
            )
        if ohabolana:
            parts.append(
                f'<div class="kbr-ohabolana"><span class="kbr-label">Ohabolana</span>'
                f'<blockquote>« {ohabolana} »</blockquote></div>'
            )
        if famaranana:
            parts.append(
                f'<div class="kbr-famaranana"><span class="kbr-label">Famaranana</span>'
                f'<p>{famaranana}</p></div>'
            )

        body = '<div class="kbr-body">' + ''.join(parts) + '</div>'
        title_text = request.POST.get('title', '').strip() or (vato or fanafahana)[:80]

        try:
            post = Post.objects.create(
                title=title_text,
                body=body,
                author=request.user,
                post_type=Post.KABARY,
            )
        except Exception as e:
            _logger.exception("Kabary create failed: %s", e)
            from django.conf import settings as _s
            err = (f'Erreur technique : {type(e).__name__}: {e}'
                   if _s.DEBUG
                   else 'Erreur lors de la création du Kabary. Réessaie dans quelques instants.')
            return JsonResponse({'ok': False, 'error': err})

        return JsonResponse({'ok': True, 'redirect': post.get_absolute_url()})

    return render(request, 'post/kabary_create.html', {})


@login_required
def vintana_create(request):
    """Crée une Capsule Vintana (time-capsule post)."""
    from django.utils import timezone

    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        title    = request.POST.get('title', '').strip()
        message  = request.POST.get('message', '').strip()
        reveal_s = request.POST.get('reveal_date', '').strip()

        # Validation
        if not message:
            err = 'Le message de la capsule est obligatoire.'
            if is_ajax:
                return JsonResponse({'ok': False, 'error': err})
            messages.error(request, err)
            return redirect('post:vintana-create')

        if not reveal_s:
            err = 'La date de révélation est obligatoire.'
            if is_ajax:
                return JsonResponse({'ok': False, 'error': err})
            messages.error(request, err)
            return redirect('post:vintana-create')

        # Parsing de la date (format HTML datetime-local : YYYY-MM-DDTHH:MM)
        try:
            from datetime import datetime
            import pytz
            naive_dt = datetime.strptime(reveal_s, '%Y-%m-%dT%H:%M')
            tz = timezone.get_current_timezone()
            reveal_dt = timezone.make_aware(naive_dt, tz)
        except ValueError:
            err = 'Format de date invalide.'
            if is_ajax:
                return JsonResponse({'ok': False, 'error': err})
            messages.error(request, err)
            return redirect('post:vintana-create')

        if reveal_dt <= timezone.now():
            err = 'La date de révélation doit être dans le futur.'
            if is_ajax:
                return JsonResponse({'ok': False, 'error': err})
            messages.error(request, err)
            return redirect('post:vintana-create')

        # Corps HTML de la capsule
        body = (
            f'<div class="vintana-body">'
            f'<p class="vintana-message">{message}</p>'
            f'</div>'
        )
        title_text = title or message[:80]

        try:
            post = Post.objects.create(
                title=title_text,
                body=body,
                author=request.user,
                post_type=Post.VINTANA,
                reveal_date=reveal_dt,
            )
        except Exception as e:
            logging.getLogger(__name__).exception("Vintana create failed: %s", e)
            err = 'Erreur lors de la création de la capsule.'
            if is_ajax:
                return JsonResponse({'ok': False, 'error': err})
            messages.error(request, err)
            return redirect('post:vintana-create')

        if is_ajax:
            return JsonResponse({'ok': True, 'redirect': post.get_absolute_url()})
        messages.success(request, 'Capsule Vintana créée ! Elle sera révélée le ' + reveal_dt.strftime('%d/%m/%Y à %H:%M') + '.')
        return redirect('post:post-detail', post_id=post.id)

    now_plus_1day = __import__('datetime').datetime.now() + __import__('datetime').timedelta(days=1)
    return render(request, 'post/vintana_create.html', {
        'min_reveal': now_plus_1day.strftime('%Y-%m-%dT%H:%M'),
    })
