from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .forms import GroupForm
from .models import Group, GroupMembership


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
    """Page de détail d'un groupe : infos, membres, actions."""
    group = get_object_or_404(Group.objects.select_related('creator'), slug=slug)
    membership = GroupMembership.objects.filter(group=group, user=request.user).first()
    is_admin = membership is not None and membership.role == GroupMembership.ADMIN
    members = group.memberships.select_related('user').all()
    return render(request, 'group/group_detail.html', {
        'group': group,
        'membership': membership,
        'is_member': membership is not None,
        'is_admin': is_admin,
        'members': members,
    })


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
