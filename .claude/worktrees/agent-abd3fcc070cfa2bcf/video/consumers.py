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

from collections import deque

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from video.models import LiveRoom

# Cache en mémoire du chunk d'initialisation par salle.
# Valide sur un seul worker (Railway free tier = 1 worker Daphne).
_init_chunks: dict = {}     # room_id (str) → { 'data': base64_str, 'mime': str }

# Ring buffer des derniers chunks media (non-init) par salle.
# Permet aux viewers qui rejoignent en cours de route d'obtenir un keyframe récent :
# VP9/VP8 insère un keyframe toutes les ~3-5 s → 20 chunks × 500 ms = 10 s de buffer
# garantissent au moins 2 keyframes → le décodeur peut démarrer proprement.
RING_BUFFER_SIZE = 12       # 12 chunks × 250 ms ≈ 3 secondes (≥ 1 keyframe VP9)
_recent_chunks: dict = {}   # room_id (str) → deque[{ 'data': str, 'mime': str }]


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
                    rid      = str(self.room_id)

                    if is_init and data_b64:
                        # Nouveau flux : réinitialiser les deux caches
                        _init_chunks[rid]   = {'data': data_b64, 'mime': mime}
                        _recent_chunks[rid] = deque(maxlen=RING_BUFFER_SIZE)
                        print(f"[LIVE {rid}] 🎬 init_chunk reçu, mime={mime}, "
                              f"taille={len(data_b64)} chars", flush=True)
                    elif data_b64:
                        # Chunk media ordinaire → ring buffer
                        if rid not in _recent_chunks:
                            _recent_chunks[rid] = deque(maxlen=RING_BUFFER_SIZE)
                        _recent_chunks[rid].append({'data': data_b64, 'mime': mime})

                    await self.channel_layer.group_send(self.room_group, {
                        'type': 'room_event',
                        'payload': {
                            'type':    'media_chunk',
                            'data':    data_b64,
                            'is_init': is_init,
                            'mime':    mime,
                        },
                    })
                else:
                    print(f"[LIVE {self.room_id}] ⚠️ media_chunk ignoré — is_host=False pour {self.user.username}", flush=True)

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
                    rid = str(self.room_id)
                    _init_chunks.pop(rid, None)
                    _recent_chunks.pop(rid, None)
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
            print(f"[LIVE {self.room_id}] ✅ host connecté : {self.user.username}", flush=True)
            # Notifier les viewers → ils renverront join_viewer
            try:
                await self.channel_layer.group_send(self.room_group, {
                    'type': 'room_event',
                    'payload': {'type': 'host_reconnected'},
                })
            except Exception:
                pass
        else:
            print(f"[LIVE {self.room_id}] ⚠️ join_host refusé pour {self.user.username} "
                  f"(host_id={getattr(room,'host_id','?')}, user_id={self.user.id})", flush=True)

    async def _handle_join_viewer(self):
        self.is_host = False
        if not self.has_joined:
            self.has_joined = True
            await self._increment_viewer_count()

        rid     = str(self.room_id)
        cached  = _init_chunks.get(rid)
        host_ch = await self._get_host_channel()

        # Envoyer le chunk d'init + les chunks récents au nouveau viewer.
        # Le ring buffer permet d'afficher quelque chose immédiatement.
        # Firefox/Opera gèrent les delta frames via auto-retry côté client.
        if cached:
            await self.send_json({
                'type':    'media_chunk',
                'data':    cached['data'],
                'mime':    cached['mime'],
                'is_init': True,
            })
            recent = list(_recent_chunks.get(rid, []))
            print(f"[LIVE {rid}] 📺 nouveau viewer {self.user.username} — "
                  f"envoi init + {len(recent)} chunks récents", flush=True)
            for chunk in recent:
                await self.send_json({
                    'type':    'media_chunk',
                    'data':    chunk['data'],
                    'mime':    chunk['mime'],
                    'is_init': False,
                })
            # Signaler au viewer que le ring buffer est épuisé → il peut syncer au live edge
            await self.send_json({'type': 'ring_buffer_done'})

        # Notifier l'hôte de l'arrivée du viewer + demander un keyframe VP9 fresh.
        # Le host redémarre son MediaRecorder → premier chunk = init + keyframe garanti.
        # _recRestartPending côté client protège contre les redémarrages multiples rapides.
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
                await self.channel_layer.send(host_ch, {
                    'type': 'direct_event',
                    'payload': {'type': 'request_keyframe'},
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
