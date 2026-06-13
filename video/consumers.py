"""
WebRTC signaling consumer for Vazimba live rooms.

Protocol (client ↔ server):

Client → Server
  {type: 'join_host'}                        — host identifies itself
  {type: 'join_viewer'}                      — viewer enters the room
  {type: 'offer',  target, sdp}              — host sends SDP offer to viewer
  {type: 'answer', target, sdp}              — viewer sends SDP answer to host
  {type: 'ice',    target, candidate}        — ICE candidate relay
  {type: 'chat',   text}                     — chat message
  {type: 'end'}                              — host ends the stream

Server → Client
  {type: 'viewer_joined', channel, username, avatar}
  {type: 'viewer_left',   channel, username}
  {type: 'offer',  sdp, from}               — host_channel in 'from'
  {type: 'answer', sdp, from}               — viewer_channel in 'from'
  {type: 'ice',    candidate, from}
  {type: 'chat',   username, avatar, text}
  {type: 'viewer_count', count}
  {type: 'stream_ended'}
  {type: 'error',  message}
"""

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class LiveConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        user = self.scope['user']
        if not user.is_authenticated:
            await self.close()
            return

        self.room_id   = self.scope['url_route']['kwargs']['room_id']
        self.room_group = f'live_{self.room_id}'
        self.user       = user
        self.is_host    = False

        room = await self._get_room()
        if not room or room.status != LiveRoom.STATUS_ACTIVE:
            await self.close()
            return

        await self.accept()
        try:
            await self.channel_layer.group_add(self.room_group, self.channel_name)
        except Exception as e:
            print(f"LiveConsumer group_add error: {e}")

    # ── Disconnect ─────────────────────────────────────────────────────────────

    async def disconnect(self, code):
        if not hasattr(self, 'room_group'):
            return

        if self.is_host:
            await self._do_end_room()
            try:
                await self.channel_layer.group_send(self.room_group, {
                    'type': 'room_event',
                    'payload': {'type': 'stream_ended'},
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
                            'channel': self.channel_name,
                            'username': self.user.username,
                        },
                    })
                except Exception:
                    pass
            await self._decrement_viewer_count()
            await self._broadcast_viewer_count()

        try:
            await self.channel_layer.group_discard(self.room_group, self.channel_name)
        except Exception:
            pass

    # ── Receive ────────────────────────────────────────────────────────────────

    async def receive_json(self, content):
        msg_type = content.get('type')
        try:
            if msg_type == 'join_host':
                await self._handle_join_host()

            elif msg_type == 'join_viewer':
                await self._handle_join_viewer()

            elif msg_type == 'offer':
                target = content.get('target')
                if target:
                    await self.channel_layer.send(target, {
                        'type': 'direct_event',
                        'payload': {
                            'type': 'offer',
                            'sdp': content.get('sdp'),
                            'from': self.channel_name,
                        },
                    })

            elif msg_type == 'answer':
                target = content.get('target')
                if target:
                    await self.channel_layer.send(target, {
                        'type': 'direct_event',
                        'payload': {
                            'type': 'answer',
                            'sdp': content.get('sdp'),
                            'from': self.channel_name,
                        },
                    })

            elif msg_type == 'ice':
                target = content.get('target')
                if target:
                    await self.channel_layer.send(target, {
                        'type': 'direct_event',
                        'payload': {
                            'type': 'ice',
                            'candidate': content.get('candidate'),
                            'from': self.channel_name,
                        },
                    })

            elif msg_type == 'chat':
                text = (content.get('text') or '').strip()[:500]
                if text:
                    avatar = await self._get_avatar_url()
                    await self.channel_layer.group_send(self.room_group, {
                        'type': 'room_event',
                        'payload': {
                            'type': 'chat',
                            'username': self.user.username,
                            'avatar': avatar,
                            'text': text,
                        },
                    })

            elif msg_type == 'end':
                if self.is_host:
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

    # ── Channel layer event handlers ────────────────────────────────────────────

    async def room_event(self, event):
        """Broadcast to all consumers in this room's group."""
        await self.send_json(event['payload'])

    async def direct_event(self, event):
        """Direct message to this specific consumer (WebRTC signaling)."""
        await self.send_json(event['payload'])

    # ── Internal helpers ───────────────────────────────────────────────────────

    async def _handle_join_host(self):
        room = await self._get_room()
        if room and str(room.host_id) == str(self.user.id):
            self.is_host = True
            await self._save_host_channel()

    async def _handle_join_viewer(self):
        self.is_host = False
        await self._increment_viewer_count()
        host_ch = await self._get_host_channel()
        if host_ch:
            try:
                avatar = await self._get_avatar_url()
                await self.channel_layer.send(host_ch, {
                    'type': 'direct_event',
                    'payload': {
                        'type': 'viewer_joined',
                        'channel': self.channel_name,
                        'username': self.user.username,
                        'avatar': avatar,
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

    # ── DB helpers (sync_to_async) ──────────────────────────────────────────────

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


