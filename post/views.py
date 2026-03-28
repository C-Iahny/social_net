from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.generic import DeleteView, UpdateView, CreateView
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

User = get_user_model()

from account.models import Account
from django.http import JsonResponse
from .forms import PostForm, EditForm, CommentForm
from .models import Post, Continent, Country, Follow, Comment
from friend.models import FriendList
from personal.models import HeroSettings


# ──────────────────────────────────────────────
# Index (legacy page)
# ──────────────────────────────────────────────
def Index(request):
    continent    = Continent.objects.all()
    countries    = Country.objects.all()
    recent_posts = Post.objects.select_related("author").order_by("-id")[:12]
    hero         = HeroSettings.get()          # singleton — crée l'instance si absente
    context = {
        "continent":    continent,
        "countries":    countries,
        "recent_posts": recent_posts,
        "hero":         hero,
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

    # Attacher les commentaires directement à chaque post (attribut dynamique)
    for post in posts_of_the_page:
        post.page_comments = comments_by_post.get(post.id, [])

    context = {
        "friends":          friends,
        "friends_count":    friends.count(),
        "posts_of_the_page": posts_of_the_page,
        "post_form":        PostForm(),
        "my_post_count":    my_post_count,
    }
    return render(request, "post/post_view.html", context)


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

        channel_layer = get_channel_layer()
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
    post = get_object_or_404(Post, id=post_id)
    if post.likes.filter(id=request.user.id).exists():
        post.likes.remove(request.user)
    else:
        post.likes.add(request.user)
    # Retourner sur la page précédente si possible
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
