from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.contrib import messages
from django.views.decorators.http import require_POST

from .models import LiveRoom


@login_required(login_url='login')
def live_list(request):
    """Page principale : liste des lives actifs + formulaire de création."""
    active_rooms = (
        LiveRoom.objects
        .filter(status=LiveRoom.STATUS_ACTIVE)
        .select_related('host', 'group')
        .order_by('-created_at')
    )
    return render(request, 'video/live_list.html', {
        'active_rooms': active_rooms,
    })


@login_required(login_url='login')
@require_POST
def live_create(request):
    """Crée un nouveau live et redirige vers la salle."""
    title    = request.POST.get('title', '').strip()
    group_id = request.POST.get('group_id', None)

    if not title:
        title = f"Live de {request.user.username}"

    group = None
    if group_id:
        try:
            from group.models import Group
            group = Group.objects.get(pk=group_id)
        except Exception:
            pass

    room = LiveRoom.objects.create(
        host=request.user,
        title=title,
        group=group,
    )
    return redirect('video:live-room', room_id=room.pk)


@login_required(login_url='login')
def live_room(request, room_id):
    """La salle live (hôte ou spectateur)."""
    room = get_object_or_404(LiveRoom, pk=room_id)

    if room.status == LiveRoom.STATUS_ENDED:
        messages.info(request, "Ce live est terminé.")
        return redirect('video:live-list')

    is_host = (room.host == request.user)

    return render(request, 'video/live_room.html', {
        'room': room,
        'is_host': is_host,
    })


@login_required(login_url='login')
@require_POST
def live_end(request, room_id):
    """Termine un live (hôte uniquement).
    Supporte deux modes :
    - Formulaire classique → redirection vers la liste
    - navigator.sendBeacon (ping de fin) → réponse 204 No Content (pas de redirection)
    """
    room = get_object_or_404(LiveRoom, pk=room_id, host=request.user)
    room.status       = LiveRoom.STATUS_ENDED
    room.ended_at     = timezone.now()
    room.host_channel = ''
    room.viewer_count = 0
    room.save(update_fields=['status', 'ended_at', 'host_channel', 'viewer_count'])

    # sendBeacon envoie Content-Type multipart/form-data, n'attend pas de redirection
    is_beacon = (request.POST.get('_beacon') == '1' or
                 'multipart' in request.content_type or
                 request.headers.get('X-Requested-With') == 'beacon')
    if is_beacon or request.headers.get('Accept') == '*/*':
        return JsonResponse({'ok': True}, status=200)
    return redirect('video:live-list')


def live_api_active(request):
    """
    JSON : live rooms actives (pour le widget feed / header).
    Accessible sans authentification pour simplifier le polling client.
    """
    rooms = (
        LiveRoom.objects
        .filter(status=LiveRoom.STATUS_ACTIVE)
        .select_related('host', 'group')
        .order_by('-created_at')[:10]
    )
    data = []
    for r in rooms:
        try:
            avatar = r.host.profile_image.url
        except Exception:
            avatar = ''
        data.append({
            'id':           r.pk,
            'title':        r.title,
            'host':         r.host.username,
            'host_avatar':  avatar,
            'viewer_count': r.viewer_count,
            'group':        r.group.name if r.group else None,
            'url':          f'/live/{r.pk}/',
        })
    return JsonResponse({'lives': data})
