from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from post.models import Post, Comment, Reaction, PostMedia, Repost
from .forms import GroupForm
from .models import Group, GroupMembership, GroupEvent


# ── Helpers réutilisés depuis post/views ──────────────────────────────────────
def _attach_media(posts, post_ids):
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


def _enrich_posts(posts, post_ids, user):
    """Attache commentaires, réactions, reposts à une liste de posts."""
    from django.db.models import Count as DjCount

    # Commentaires
    comments_all = list(
        Comment.objects.filter(post_id__in=post_ids)
        .select_related('author').order_by('created_at')
    )
    top_by_post = {}
    replies_map = {}
    for c in comments_all:
        if c.parent_id is None:
            top_by_post.setdefault(c.post_id, []).append(c)
        else:
            replies_map.setdefault(c.parent_id, []).append(c)
    for clist in top_by_post.values():
        for c in clist:
            c.reply_list = replies_map.get(c.id, [])

    # Réactions
    reactions_qs = (
        Reaction.objects.filter(post_id__in=post_ids)
        .values('post_id', 'reaction_type')
        .annotate(c=DjCount('id'))
    )
    reactions_by_post = {}
    for row in reactions_qs:
        reactions_by_post.setdefault(row['post_id'], {})[row['reaction_type']] = row['c']

    user_reactions = {}
    if user.is_authenticated:
        for pid, rtype in Reaction.objects.filter(
            post_id__in=post_ids, user=user
        ).values_list('post_id', 'reaction_type'):
            user_reactions[pid] = rtype

    # Reposts
    try:
        counts_qs = Repost.objects.filter(post_id__in=post_ids).values('post_id').annotate(c=DjCount('id'))
        count_map = {row['post_id']: row['c'] for row in counts_qs}
        user_reposts = set(
            Repost.objects.filter(post_id__in=post_ids, user=user).values_list('post_id', flat=True)
        ) if user.is_authenticated else set()
    except Exception:
        count_map = {}
        user_reposts = set()

    for post in posts:
        top = top_by_post.get(post.id, [])
        for c in top:
            if not hasattr(c, 'reply_list'):
                c.reply_list = []
        post.page_comments   = top
        post.total_comments  = len(top) + sum(len(c.reply_list) for c in top)
        post.reaction_counts = reactions_by_post.get(post.id, {})
        post.user_reaction   = user_reactions.get(post.id)
        post.total_reactions = sum(post.reaction_counts.values())
        post.repost_count    = count_map.get(post.id, 0)
        post.user_reposted   = post.id in user_reposts

    _attach_media(posts, post_ids)


# ── Vues ──────────────────────────────────────────────────────────────────────

@login_required
def group_list(request):
    """Liste de tous les groupes + indication d'appartenance."""
    groups = (
        Group.objects
        .annotate(num_members=Count('memberships'))
        .select_related('creator')
    )
    my_group_ids = set(
        GroupMembership.objects
        .filter(user=request.user)
        .values_list('group_id', flat=True)
    )
    return render(request, 'group/group_list.html', {
        'groups': groups,
        'my_group_ids': my_group_ids,
    })


@login_required
def group_create(request):
    """Création d'un groupe — le créateur devient admin du groupe."""
    if request.method == 'POST':
        form = GroupForm(request.POST, request.FILES)
        if form.is_valid():
            group = form.save(commit=False)
            group.creator = request.user
            group.save()
            GroupMembership.objects.create(
                user=request.user,
                group=group,
                role=GroupMembership.ADMIN,
            )
            messages.success(request, "Groupe créé avec succès.")
            return redirect('group:detail', slug=group.slug)
    else:
        form = GroupForm()
    return render(request, 'group/group_form.html', {
        'form': form,
        'is_create': True,
    })


@login_required
def group_detail(request, slug):
    """Page de détail d'un groupe : infos, membres, posts, actions."""
    group = get_object_or_404(Group.objects.select_related('creator'), slug=slug)
    membership = GroupMembership.objects.filter(group=group, user=request.user).first()
    is_admin = membership is not None and membership.role == GroupMembership.ADMIN
    is_mod   = membership is not None and membership.role in (GroupMembership.ADMIN, GroupMembership.MODERATOR)
    is_member = membership is not None
    members = group.memberships.select_related('user').all()

    # ── Annonces épinglées ────────────────────────────────────────
    pinned_posts = list(
        Post.objects.filter(group=group, is_pinned=True)
        .select_related('author', 'group')
        .order_by('-id')
    )
    pinned_ids = [p.id for p in pinned_posts]
    if pinned_posts:
        _enrich_posts(pinned_posts, pinned_ids, request.user)

    # ── Posts du groupe (hors épinglés, paginés, 10/page) ────────
    posts_qs = (
        Post.objects.filter(group=group, is_pinned=False)
        .select_related('author', 'group')
        .order_by('-id')
    )
    paginator = Paginator(posts_qs, 10)
    page_number = request.GET.get('page', 1)
    posts_page = paginator.get_page(page_number)
    post_ids = [p.id for p in posts_page]
    _enrich_posts(posts_page, post_ids, request.user)

    # ── Galerie médias ────────────────────────────────────────────
    media_qs = (
        PostMedia.objects.filter(post__group=group)
        .select_related('post', 'post__author')
        .order_by('-post__id')
    )
    media_images = [m for m in media_qs if m.media_type == 'image']
    media_videos = [m for m in media_qs if m.media_type == 'video']

    # ── Événements à venir ────────────────────────────────────────
    upcoming_events = group.events.filter(
        event_date__gte=timezone.now()
    ).select_related('organizer').prefetch_related('attendees')[:5]

    # ── Statistiques ──────────────────────────────────────────────
    post_count   = Post.objects.filter(group=group).count()
    member_count = group.memberships.count()

    return render(request, 'group/group_detail.html', {
        'group':           group,
        'membership':      membership,
        'is_member':       is_member,
        'is_admin':        is_admin,
        'is_mod':          is_mod,
        'members':         members,
        'pinned_posts':    pinned_posts,
        'posts_of_the_page': posts_page,
        'media_images':    media_images,
        'media_videos':    media_videos,
        'upcoming_events': upcoming_events,
        'post_count':      post_count,
        'member_count':    member_count,
        'comment_url_template': '/post/{post_id}/add-comment/',
    })


@login_required
def group_add_post(request, slug):
    """Créer un post dans un groupe (AJAX ou POST classique)."""
    group = get_object_or_404(Group, slug=slug)
    # Vérifier que l'utilisateur est membre
    if not GroupMembership.objects.filter(group=group, user=request.user).exists():
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'error': 'Non membre'}, status=403)
        return HttpResponseForbidden("Vous devez être membre du groupe pour publier.")

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        body  = request.POST.get('body', '').strip()
        files = request.FILES.getlist('media_files')

        # Un post est valide s'il a du texte OU des fichiers
        if not title and not body and not files:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': False, 'error': 'Contenu vide'})
            messages.error(request, "Le post ne peut pas être vide.")
            return redirect('group:detail', slug=group.slug)

        post = Post.objects.create(
            title=title or (body[:80] if body else ''),
            body=body,
            author=request.user,
            group=group,
        )

        # ── Enregistrer les médias ────────────────────────────────────
        _VIDEO_EXTS = {'mp4', 'webm', 'ogg', 'mov', 'mkv', 'avi', 'm4v', '3gp'}
        for i, f in enumerate(files):
            ext = f.name.rsplit('.', 1)[-1].lower() if '.' in f.name else ''
            mtype = 'video' if ext in _VIDEO_EXTS else 'image'
            try:
                PostMedia.objects.create(post=post, file=f, media_type=mtype, order=i)
            except Exception as e:
                import logging
                logging.getLogger(__name__).exception("GroupPost: PostMedia FAILED (%s): %s", f.name, e)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.template.loader import render_to_string
            _enrich_posts([post], [post.id], request.user)
            html = render_to_string(
                'post/post_cards_fragment.html',
                {'posts_of_the_page': [post], 'request': request},
                request=request,
            )
            return JsonResponse({'ok': True, 'html': html})

        messages.success(request, "Post publié dans le groupe.")
        return redirect('group:detail', slug=group.slug)

    return redirect('group:detail', slug=group.slug)


@login_required
def group_join(request, slug):
    """Rejoindre un groupe (POST)."""
    group = get_object_or_404(Group, slug=slug)
    if request.method == 'POST':
        _, created = GroupMembership.objects.get_or_create(
            user=request.user,
            group=group,
            defaults={'role': GroupMembership.MEMBER},
        )
        if created:
            messages.success(request, "Vous avez rejoint le groupe.")
    return redirect('group:detail', slug=group.slug)


@login_required
def group_leave(request, slug):
    """Quitter un groupe (POST). Le créateur ne peut pas quitter."""
    group = get_object_or_404(Group, slug=slug)
    if request.method == 'POST':
        if request.user == group.creator:
            messages.error(request, "Le créateur ne peut pas quitter son propre groupe.")
        else:
            GroupMembership.objects.filter(user=request.user, group=group).delete()
            messages.success(request, "Vous avez quitté le groupe.")
    return redirect('group:detail', slug=group.slug)


@login_required
def group_pin_post(request, slug, post_id):
    """Épingler / désépingler un post (admin ou modérateur)."""
    group = get_object_or_404(Group, slug=slug)
    membership = GroupMembership.objects.filter(group=group, user=request.user).first()
    is_mod = membership and membership.role in (GroupMembership.ADMIN, GroupMembership.MODERATOR)
    if not is_mod:
        return JsonResponse({'ok': False, 'error': 'Non autorisé'}, status=403)
    post = get_object_or_404(Post, pk=post_id, group=group)
    post.is_pinned = not post.is_pinned
    post.save(update_fields=['is_pinned'])
    return JsonResponse({'ok': True, 'pinned': post.is_pinned})


@login_required
def group_promote_member(request, slug, user_id):
    """Promouvoir un membre en modérateur (admin seulement)."""
    group = get_object_or_404(Group, slug=slug)
    if not GroupMembership.objects.filter(group=group, user=request.user, role=GroupMembership.ADMIN).exists():
        return HttpResponseForbidden()
    from account.models import Account
    target = get_object_or_404(Account, pk=user_id)
    m = get_object_or_404(GroupMembership, group=group, user=target)
    if m.role == GroupMembership.MEMBER:
        m.role = GroupMembership.MODERATOR
        m.save(update_fields=['role'])
        messages.success(request, f"{target.username} est maintenant modérateur.")
    return redirect('group:detail', slug=slug)


@login_required
def group_demote_member(request, slug, user_id):
    """Rétrograder un modérateur en membre (admin seulement)."""
    group = get_object_or_404(Group, slug=slug)
    if not GroupMembership.objects.filter(group=group, user=request.user, role=GroupMembership.ADMIN).exists():
        return HttpResponseForbidden()
    from account.models import Account
    target = get_object_or_404(Account, pk=user_id)
    m = get_object_or_404(GroupMembership, group=group, user=target)
    if m.role == GroupMembership.MODERATOR:
        m.role = GroupMembership.MEMBER
        m.save(update_fields=['role'])
        messages.success(request, f"{target.username} est maintenant membre.")
    return redirect('group:detail', slug=slug)


@login_required
def group_kick_member(request, slug, user_id):
    """Retirer un membre du groupe (admin ou modérateur)."""
    if request.method != 'POST':
        return redirect('group:detail', slug=slug)
    group = get_object_or_404(Group, slug=slug)
    membership = GroupMembership.objects.filter(group=group, user=request.user).first()
    is_mod = membership and membership.role in (GroupMembership.ADMIN, GroupMembership.MODERATOR)
    if not is_mod:
        return JsonResponse({'ok': False, 'error': 'Non autorisé'}, status=403)
    from account.models import Account
    target = get_object_or_404(Account, pk=user_id)
    if target == request.user:
        return JsonResponse({'ok': False, 'error': 'Vous ne pouvez pas vous retirer vous-même.'}, status=400)
    if target == group.creator:
        return JsonResponse({'ok': False, 'error': 'Impossible de retirer le créateur du groupe.'}, status=403)
    # Un modérateur ne peut pas expulser un autre modérateur ni un admin
    target_membership = GroupMembership.objects.filter(group=group, user=target).first()
    if target_membership and target_membership.role in (GroupMembership.ADMIN, GroupMembership.MODERATOR):
        if membership.role != GroupMembership.ADMIN:
            return JsonResponse({'ok': False, 'error': 'Seul un admin peut retirer un modérateur.'}, status=403)
    if target_membership:
        target_membership.delete()
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        return JsonResponse({'ok': True, 'username': target.username})
    messages.success(request, f"{target.username} a été retiré du groupe.")
    return redirect('group:detail', slug=slug)


@login_required
def group_event_create(request, slug):
    """Créer un événement dans le groupe (membre)."""
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    group = get_object_or_404(Group, slug=slug)

    if not GroupMembership.objects.filter(group=group, user=request.user).exists():
        if is_ajax:
            return JsonResponse({'ok': False, 'error': 'Vous devez être membre du groupe.'}, status=403)
        return HttpResponseForbidden()

    if request.method != 'POST':
        if is_ajax:
            return JsonResponse({'ok': False, 'error': 'Méthode non autorisée.'}, status=405)
        return redirect('group:detail', slug=slug)

    title       = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    location    = request.POST.get('location', '').strip()
    event_date  = request.POST.get('event_date', '').strip()

    if not title:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': 'Le titre est obligatoire.'})
        messages.error(request, "Le titre est obligatoire.")
        return redirect('group:detail', slug=slug)

    if not event_date:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': 'La date est obligatoire.'})
        messages.error(request, "La date est obligatoire.")
        return redirect('group:detail', slug=slug)

    # parse_datetime accepte "2026-06-11T14:30" (format datetime-local HTML)
    from django.utils.dateparse import parse_datetime
    dt = parse_datetime(event_date)
    if dt is None:
        # Essayer en ajoutant ":00" si les secondes manquent
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(event_date)
        except ValueError:
            dt = None

    if dt is None:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': f'Format de date invalide : {event_date!r}'})
        messages.error(request, "Format de date invalide.")
        return redirect('group:detail', slug=slug)

    try:
        GroupEvent.objects.create(
            group=group, organizer=request.user,
            title=title, description=description,
            location=location, event_date=dt,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("GroupEvent create failed: %s", e)
        if is_ajax:
            return JsonResponse({'ok': False, 'error': 'Erreur serveur. Les migrations ont-elles été appliquées ?'})
        messages.error(request, "Erreur lors de la création de l'événement.")
        return redirect('group:detail', slug=slug)

    if is_ajax:
        return JsonResponse({'ok': True, 'message': 'Événement créé avec succès !'})
    messages.success(request, "Événement créé.")
    return redirect('group:detail', slug=slug)


@login_required
def group_invite_search(request, slug):
    """Recherche AJAX d'utilisateurs à inviter dans le groupe."""
    group = get_object_or_404(Group, slug=slug)
    membership = GroupMembership.objects.filter(group=group, user=request.user).first()
    is_mod = membership and membership.role in (GroupMembership.ADMIN, GroupMembership.MODERATOR)
    if not is_mod:
        return JsonResponse({'ok': False, 'error': 'Non autorisé'}, status=403)

    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'users': []})

    from account.models import Account
    # Exclure les membres déjà dans le groupe
    already_ids = set(GroupMembership.objects.filter(group=group).values_list('user_id', flat=True))
    users = (
        Account.objects.filter(
            Q(username__icontains=query) | Q(email__icontains=query)
        ).exclude(pk__in=already_ids)[:10]
    )
    data = []
    for u in users:
        avatar = None
        try:
            avatar = u.profile_image.url if u.profile_image else None
        except Exception:
            pass
        data.append({'id': u.id, 'username': u.username, 'avatar': avatar})
    return JsonResponse({'ok': True, 'users': data})


@login_required
def group_invite_member(request, slug):
    """Ajouter directement un utilisateur au groupe (admin/mod)."""
    group = get_object_or_404(Group, slug=slug)
    membership = GroupMembership.objects.filter(group=group, user=request.user).first()
    is_mod = membership and membership.role in (GroupMembership.ADMIN, GroupMembership.MODERATOR)
    if not is_mod:
        return JsonResponse({'ok': False, 'error': 'Non autorisé'}, status=403)

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        from account.models import Account
        try:
            target = Account.objects.get(pk=user_id)
        except Account.DoesNotExist:
            return JsonResponse({'ok': False, 'error': 'Utilisateur introuvable'})

        _, created = GroupMembership.objects.get_or_create(
            user=target, group=group,
            defaults={'role': GroupMembership.MEMBER},
        )
        return JsonResponse({
            'ok': True,
            'created': created,
            'username': target.username,
            'message': f"{target.username} a été ajouté au groupe." if created else f"{target.username} est déjà membre.",
        })
    return JsonResponse({'ok': False, 'error': 'Méthode non autorisée'}, status=405)


@login_required
def group_dina_save(request, slug):
    """Sauvegarder le Dina du groupe (admin seulement) en AJAX."""
    group = get_object_or_404(Group, slug=slug)
    is_admin = GroupMembership.objects.filter(
        group=group, user=request.user, role=GroupMembership.ADMIN
    ).exists()
    if not is_admin and request.user != group.creator:
        return JsonResponse({'ok': False, 'error': 'Non autorisé'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Méthode non autorisée'}, status=405)
    dina = request.POST.get('dina', '').strip()
    if len(dina) > 3000:
        return JsonResponse({'ok': False, 'error': 'Le Dina est trop long (max 3000 caractères).'})
    group.dina = dina
    group.save(update_fields=['dina'])
    return JsonResponse({'ok': True, 'message': 'Dina sauvegardé.'})


@login_required
def group_event_attend(request, slug, event_id):
    """Participer / annuler participation à un événement."""
    group = get_object_or_404(Group, slug=slug)
    event = get_object_or_404(GroupEvent, pk=event_id, group=group)
    if request.user in event.attendees.all():
        event.attendees.remove(request.user)
        attending = False
    else:
        event.attendees.add(request.user)
        attending = True
    return JsonResponse({'ok': True, 'attending': attending, 'count': event.attendees.count()})


@login_required
def group_edit(request, slug):
    """Édition d'un groupe — réservée au créateur ou à un admin du groupe."""
    group = get_object_or_404(Group, slug=slug)
    membership = GroupMembership.objects.filter(group=group, user=request.user).first()
    is_admin = membership is not None and membership.role == GroupMembership.ADMIN
    if not (request.user == group.creator or is_admin):
        return HttpResponseForbidden("Action non autorisée.")

    if request.method == 'POST':
        form = GroupForm(request.POST, request.FILES, instance=group)
        if form.is_valid():
            form.save()
            messages.success(request, "Groupe mis à jour.")
            return redirect('group:detail', slug=group.slug)
    else:
        form = GroupForm(instance=group)
    return render(request, 'group/group_form.html', {
        'form': form,
        'is_create': False,
        'group': group,
    })


@login_required
def group_delete(request, slug):
    """Suppression d'un groupe — réservée au créateur."""
    group = get_object_or_404(Group, slug=slug)
    if request.user != group.creator:
        return HttpResponseForbidden("Seul le créateur peut supprimer le groupe.")
    if request.method == 'POST':
        group.delete()
        messages.success(request, "Groupe supprimé.")
        return redirect('group:list')
    return render(request, 'group/group_confirm_delete.html', {'group': group})
