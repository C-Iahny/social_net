from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.generic import DeleteView, UpdateView, CreateView
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.template.loader import render_to_string
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

User = get_user_model()

from account.models import Account
from django.http import JsonResponse
from .forms import PostForm, EditForm, CommentForm
from .models import Post, Continent, Country, Follow, Comment, Reaction
from friend.models import FriendList
from personal.models import HeroSettings


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
    feed_posts = Post.objects.filter(
        author__in=list(friends) + [user]
    ).order_by("-id")

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
    comments_qs = CommentModel.objects.filter(
        post_id__in=post_ids
    ).select_related('author').order_by('created_at')
    comments_by_post = {}
    for c in comments_qs:
        comments_by_post.setdefault(c.post_id, []).append(c)

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
        post.page_comments     = comments_by_post.get(post.id, [])
        post.reaction_counts   = reactions_by_post.get(post.id, {})
        post.user_reaction     = user_reaction_by_post.get(post.id)
        post.total_reactions   = sum(post.reaction_counts.values())

    context = {
        "friends":          friends,
        "friends_count":    friends.count(),
        "posts_of_the_page": posts_of_the_page,
        "post_form":        PostForm(),
        "my_post_count":    my_post_count,
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
    ).order_by("-id")

    paginator = Paginator(feed_posts, 5)
    page_number = request.GET.get("page", 1)
    posts_page = paginator.get_page(page_number)

    # Précharger les commentaires
    post_ids = [p.id for p in posts_page]
    from .models import Comment as CommentModel
    comments_qs = CommentModel.objects.filter(
        post_id__in=post_ids
    ).select_related('author').order_by('created_at')
    comments_by_post = {}
    for c in comments_qs:
        comments_by_post.setdefault(c.post_id, []).append(c)

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
        post.page_comments   = comments_by_post.get(post.id, [])
        post.reaction_counts = reactions_by_post.get(post.id, {})
        post.user_reaction   = user_reaction_by_post.get(post.id)
        post.total_reactions = sum(post.reaction_counts.values())

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

        # Notify each friend via WebSocket channel layer
        post = self.object
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
        comment.save()

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
        })

    return JsonResponse({"error": "Commentaire invalide."}, status=400)


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
    ).select_related('author').order_by('-id')

    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    posts_page = paginator.get_page(page_number)

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
