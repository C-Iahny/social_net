"""
Live streaming consumer for Vazimba — MediaRecorder → WebSocket → MediaSource.

Architecture : le host encode son écran/caméra avec MediaRecorder (WebM/VP8),
envoie les chunks en base64 via WebSocket au serveur Django Channels, qui les
diffuse à tous les viewers. Pas de WebRTC P2P, donc aucun problème de NAT/TURN.

Protocol (client → server):
  {type: 'join_host'}
  {type: 'join_viewer'}
  {type: 'media_chunk', data: <base64>, is_init: bool, mime: str}
  {type: 'chat',  text}
  {type: 'end'}

Protocol (server → client):
  {type: 'viewer_joined',    username, avatar}
  {type: 'viewer_left',      username}
  {type: 'media_chunk',      data, is_init, mime}
  {type: 'host_disconnected'}
  {type: 'host_reconnected'}
  {type: 'chat',             username, avatar, text}
  {type: 'viewer_count',     count}
  {type: 'stream_ended'}
"""

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from video.models import LiveRoom

# Cache en mémoire du chunk d'initialisation par salle.
# Valide sur un seul worker (Railway free tier = 1 worker Daphne).
# Permet aux viewers qui rejoignent en cours de route de recevoir l'init WebM.
_init_chunks: dict = {}   # room_id (str) → { 'data': base64_str, 'mime': str }


class LiveConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        user = self.scope['user']
        if not user.is_authenticated:
            await self.close()
            return

        self.room_id    = self.scope['url_route']['kwargs']['room_id']
        self.room_group = f'live_{self.room_id}'
        self.user       = user
        self.is_host    = False
        self.has_joined = False   # viewers : évite le double-comptage sur rejoin

        room = await self._get_room()
        if not room or room.status != LiveRoom.STATUS_ACTIVE:
            await self.close()
            return

        await self.accept()
        try:
            await self.channel_layer.group_add(self.room_group, self.channel_name)
        except Exception as e:
            print(f"LiveConsumer group_add error: {e}")

    # ── Disconnect ──────────────────────────────────────────────────────────────

    async def disconnect(self, code):
        if not hasattr(self, 'room_group'):
            return

        if self.is_host:
            # Ne PAS terminer le room — l'hôte peut revenir.
            await self._clear_host_channel()
            try:
                await self.channel_layer.group_send(self.room_group, {
                    'type': 'room_event',
                    'payload': {'type': 'host_disconnected'},
                })
            except Exception:
                pass
        else:
            host_ch = await self._get_host_channel()
            if host_ch:
                try:
                    await self.channel_layer.send(host_ch, {
                        'type': 'direct_event',
                        'payload': {
                            'type': 'viewer_left',
                            'username': self.user.username,
                        },
                    })
                except Exception:
                    pass
            if self.has_joined:
                await self._decrement_viewer_count()
                await self._broadcast_viewer_count()

        try:
            await self.channel_layer.group_discard(self.room_group, self.channel_name)
        except Exception:
            pass

    # ── Receive ─────────────────────────────────────────────────────────────────

    async def receive_json(self, content):
        msg_type = content.get('type')
        try:
            if msg_type == 'join_host':
                await self._handle_join_host()

            elif msg_type == 'join_viewer':
                await self._handle_join_viewer()

            elif msg_type == 'media_chunk':
                if self.is_host:
                    data_b64 = content.get('data', '')
                    is_init  = bool(content.get('is_init', False))
                    mime     = content.get('mime', 'video/webm;codecs=vp8,opus')

                    # Mettre en cache le chunk d'initialisation
                    if is_init and data_b64:
                        _init_chunks[str(self.room_id)] = {'data': data_b64, 'mime': mime}

                    await self.channel_layer.group_send(self.room_group, {
                        'type': 'room_event',
                        'payload': {
                            'type':    'media_chunk',
                            'data':    data_b64,
                            'is_init': is_init,
                            'mime':    mime,
                        },
                    })

            elif msg_type == 'chat':
                text = (content.get('text') or '').strip()[:500]
                if text:
                    avatar = await self._get_avatar_url()
                    await self.channel_layer.group_send(self.room_group, {
                        'type': 'room_event',
                        'payload': {
                            'type':     'chat',
                            'username': self.user.username,
                            'avatar':   avatar,
                            'text':     text,
                        },
                    })

            elif msg_type == 'end':
                if self.is_host:
                    _init_chunks.pop(str(self.room_id), None)
                    await self._do_end_room()
                    await self.channel_layer.group_send(self.room_group, {
                        'type': 'room_event',
                        'payload': {'type': 'stream_ended'},
                    })

        except Exception as e:
            print(f"LiveConsumer receive_json error: {e}")
            try:
                await self.send_json({'type': 'error', 'message': str(e)})
            except Exception:
                pass

    # ── Channel layer handlers ───────────────────────────────────────────────────

    async def room_event(self, event):
        await self.send_json(event['payload'])

    async def direct_event(self, event):
        await self.send_json(event['payload'])

    # ── Internal helpers ─────────────────────────────────────────────────────────

    async def _handle_join_host(self):
        room = await self._get_room()
        if room and str(room.host_id) == str(self.user.id):
            self.is_host = True
            await self._save_host_channel()
            # Notifier les viewers → ils renverront join_viewer
            try:
                await self.channel_layer.group_send(self.room_group, {
                    'type': 'room_event',
                    'payload': {'type': 'host_reconnected'},
                })
            except Exception:
                pass

    async def _handle_join_viewer(self):
        self.is_host = False
        if not self.has_joined:
            self.has_joined = True
            await self._increment_viewer_count()

        # Envoyer immédiatement le chunk d'init si on l'a en cache
        cached = _init_chunks.get(str(self.room_id))
        if cached:
            await self.send_json({
                'type':    'media_chunk',
                'data':    cached['data'],
                'mime':    cached['mime'],
                'is_init': True,
            })

        # Notifier l'hôte
        host_ch = await self._get_host_channel()
        if host_ch:
            try:
                avatar = await self._get_avatar_url()
                await self.channel_layer.send(host_ch, {
                    'type': 'direct_event',
                    'payload': {
                        'type':     'viewer_joined',
                        'username': self.user.username,
                        'avatar':   avatar,
                    },
                })
            except Exception as e:
                print(f"LiveConsumer notify host error: {e}")

        await self._broadcast_viewer_count()

    async def _broadcast_viewer_count(self):
        try:
            count = await self._get_viewer_count()
            await self.channel_layer.group_send(self.room_group, {
                'type': 'room_event',
                'payload': {'type': 'viewer_count', 'count': count},
            })
        except Exception:
            pass

    # ── DB helpers (sync_to_async) ────────────────────────────────────────────────

    @database_sync_to_async
    def _get_room(self):
        from video.models import LiveRoom
        try:
            return LiveRoom.objects.select_related('host').get(id=self.room_id)
        except LiveRoom.DoesNotExist:
            return None

    @database_sync_to_async
    def _get_host_channel(self):
        from video.models import LiveRoom
        try:
            r = LiveRoom.objects.get(id=self.room_id, status=LiveRoom.STATUS_ACTIVE)
            return r.host_channel or None
        except LiveRoom.DoesNotExist:
            return None

    @database_sync_to_async
    def _save_host_channel(self):
        from video.models import LiveRoom
        LiveRoom.objects.filter(id=self.room_id).update(host_channel=self.channel_name)

    @database_sync_to_async
    def _clear_host_channel(self):
        from video.models import LiveRoom
        LiveRoom.objects.filter(id=self.room_id).update(host_channel='')

    @database_sync_to_async
    def _do_end_room(self):
        from video.models import LiveRoom
        LiveRoom.objects.filter(id=self.room_id).update(
            status=LiveRoom.STATUS_ENDED,
            ended_at=timezone.now(),
            viewer_count=0,
            host_channel='',
        )

    @database_sync_to_async
    def _increment_viewer_count(self):
        from video.models import LiveRoom
        from django.db.models import F
        LiveRoom.objects.filter(id=self.room_id, status=LiveRoom.STATUS_ACTIVE).update(
            viewer_count=F('viewer_count') + 1
        )

    @database_sync_to_async
    def _decrement_viewer_count(self):
        from video.models import LiveRoom
        from django.db.models import F, Value
        from django.db.models.functions import Greatest
        LiveRoom.objects.filter(id=self.room_id, status=LiveRoom.STATUS_ACTIVE).update(
            viewer_count=Greatest(F('viewer_count') - 1, Value(0))
        )

    @database_sync_to_async
    def _get_viewer_count(self):
        from video.models import LiveRoom
        try:
            return LiveRoom.objects.get(id=self.room_id).viewer_count
        except LiveRoom.DoesNotExist:
            return 0

    @database_sync_to_async
    def _get_avatar_url(self):
        try:
            return self.user.profile_image.url
        except Exception:
            return '/static/images/default_profile_image.png'
