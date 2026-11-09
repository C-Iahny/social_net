"""
Non-lus du chat : ouvrir la conversation doit remettre le compteur à zéro
et faire disparaître la notification de la cloche « Messages ».
"""
import asyncio

from channels.testing import WebsocketCommunicator
from django.contrib.contenttypes.models import ContentType
from django.test import TransactionTestCase
from django.utils.functional import SimpleLazyObject

from account.models import Account
from chat.consumers import ChatConsumer
from chat.models import PrivateChatRoom, UnreadChatRoomMessages
from notification.models import Notification


def mk(name):
    return Account.objects.create_user(email=f'{name}@test.mg', username=name, password='x12345678')


class ChatUnreadResetTests(TransactionTestCase):
    def _comm(self, user, lazy=False):
        comm = WebsocketCommunicator(ChatConsumer.as_asgi(), '/chat/1/')
        comm.scope['user'] = SimpleLazyObject(lambda: user) if lazy else user
        return comm

    def _run(self, lazy):
        a, b = mk('alice'), mk('bob')
        room = PrivateChatRoom.objects.create(user1=a, user2=b, is_active=True)
        chat_ct = ContentType.objects.get_for_model(UnreadChatRoomMessages)

        async def scenario():
            ca = self._comm(a, lazy)
            await ca.connect()
            await ca.send_json_to({'command': 'join', 'room': str(room.id)})
            await ca.receive_json_from()            # {"join": id}
            await ca.send_json_to({'command': 'send', 'room': str(room.id), 'message': 'salut'})
            await asyncio.sleep(0.3)
            cb = self._comm(b, lazy)
            await cb.connect()
            await cb.send_json_to({'command': 'join', 'room': str(room.id)})
            await cb.receive_json_from()
            await asyncio.sleep(0.3)
            await ca.disconnect(); await cb.disconnect()

        asyncio.get_event_loop().run_until_complete(scenario()) if False else asyncio.run(scenario())
        unread_b = UnreadChatRoomMessages.objects.get(room=room, user=b)
        notifs_b = Notification.objects.filter(target=b, content_type=chat_ct)
        return unread_b.count, notifs_b.count()

    def test_join_resets_unread_plain_user(self):
        self.assertEqual(self._run(lazy=False), (0, 0))

    def test_join_resets_unread_lazy_user(self):
        self.assertEqual(self._run(lazy=True), (0, 0))


class RealtimeNotificationTests(TransactionTestCase):
    """Diffusion temps réel par signal, badges, lecture au clic, présence."""

    def setUp(self):
        self.a, self.b = mk('ana'), mk('ben')
        self.room = PrivateChatRoom.objects.create(user1=self.a, user2=self.b, is_active=True)
        self.chat_ct = ContentType.objects.get_for_model(UnreadChatRoomMessages)

    def _notif_comm(self, user):
        from notification.consumers import NotificationConsumer
        comm = WebsocketCommunicator(NotificationConsumer.as_asgi(), '/')
        comm.scope['user'] = user
        return comm

    def _chat_comm(self, user):
        comm = WebsocketCommunicator(ChatConsumer.as_asgi(), '/chat/%d/' % self.room.id)
        comm.scope['user'] = user
        return comm

    async def _drain(self, comm, want, timeout=2):
        """Lit les trames jusqu'à trouver `want(data)` vrai."""
        import time
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                data = await comm.receive_json_from(timeout=0.5)
            except Exception:
                continue
            if want(data):
                return data
        self.fail('trame attendue non reçue')

    def test_post_notification_pushed_to_bell_without_manual_send(self):
        from channels.db import database_sync_to_async
        from post.models import Post
        from notification.models import Notification
        post_ct = ContentType.objects.get_for_model(Post)
        post = Post.objects.create(author=self.b, title='t', body='b', status='published')

        async def scenario():
            comm = self._notif_comm(self.b)
            await comm.connect()
            await database_sync_to_async(Notification.objects.create)(
                target=self.b, from_user=self.a, verb='ana a réagi à votre post',
                content_type=post_ct, object_id=str(post.id), redirect_url='http://127.0.0.1/feed/')
            new = await self._drain(comm, lambda d: d.get('general_msg_type') == 3)
            self.assertEqual(new['notifications'][0]['verb'], 'ana a réagi à votre post')
            cnt = await self._drain(comm, lambda d: d.get('general_msg_type') == 4)
            self.assertEqual(cnt['count'], 1)
            await comm.disconnect()
        asyncio.run(scenario())

    def test_chat_message_pushes_badge_then_open_room_clears_it(self):
        async def scenario():
            bell = self._notif_comm(self.b)
            await bell.connect()
            ca = self._chat_comm(self.a)
            await ca.connect()
            await ca.send_json_to({'command': 'join', 'room': str(self.room.id)})
            await ca.send_json_to({'command': 'send', 'room': str(self.room.id), 'message': 'salut ben'})
            push = await self._drain(bell, lambda d: d.get('msg_type') == 10)
            self.assertEqual(push['count'], 1)
            # Ben ouvre la conversation : la notification disparaît et les badges sont renvoyés
            cb = self._chat_comm(self.b)
            await cb.connect()
            await cb.send_json_to({'command': 'join', 'room': str(self.room.id)})
            cnt = await self._drain(bell, lambda d: d.get('chat_msg_type') == 14)
            self.assertEqual(cnt['count'], 0)
            await ca.disconnect(); await cb.disconnect(); await bell.disconnect()
        asyncio.run(scenario())
        self.assertEqual(Notification.objects.filter(target=self.b, content_type=self.chat_ct).count(), 0)

    def test_chat_socket_survives_bell_events(self):
        from channels.layers import get_channel_layer

        async def scenario():
            cb = self._chat_comm(self.b)
            await cb.connect()
            await cb.send_json_to({'command': 'join', 'room': str(self.room.id)})
            await self._drain(cb, lambda d: 'join' in d)
            await get_channel_layer().group_send('user_%d' % self.b.id, {
                'type': 'post_action_notification', 'notification': {'notification_id': '1'}})
            await get_channel_layer().group_send('user_%d' % self.b.id, {'type': 'notif.counts'})
            await asyncio.sleep(0.2)
            await cb.send_json_to({'command': 'get_user_info', 'room_id': str(self.room.id)})
            await self._drain(cb, lambda d: 'user_info' in d)
            await cb.disconnect()
        asyncio.run(scenario())

    def test_opening_chat_page_resets_unread(self):
        from django.test import Client
        unread = UnreadChatRoomMessages.objects.get(room=self.room, user=self.b)
        unread.count = 2; unread.most_recent_message = 'yo'; unread.save()
        self.assertEqual(Notification.objects.filter(target=self.b, content_type=self.chat_ct).count(), 1)
        c = Client(HTTP_HOST='127.0.0.1'); c.force_login(self.b)
        r = c.get('/chat/?room_id=%d' % self.room.id)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(UnreadChatRoomMessages.objects.get(room=self.room, user=self.b).count, 0)
        self.assertEqual(Notification.objects.filter(target=self.b, content_type=self.chat_ct).count(), 0)
        self.assertEqual(c.get('/notif/counts/').json(), {'general': 0, 'chat': 0})

    def test_mark_single_notification_read_http_and_ws(self):
        from django.test import Client
        from post.models import Post
        post_ct = ContentType.objects.get_for_model(Post)
        post = Post.objects.create(author=self.b, title='t', body='b', status='published')
        n1 = Notification.objects.create(target=self.b, from_user=self.a, verb='x', content_type=post_ct, object_id=str(post.id))
        n2 = Notification.objects.create(target=self.b, from_user=self.a, verb='y', content_type=post_ct, object_id=str(post.id))
        c = Client(HTTP_HOST='127.0.0.1'); c.force_login(self.b)
        r = c.post('/notif/read/%d/' % n1.id)
        self.assertEqual(r.json()['general'], 1)
        self.assertTrue(Notification.objects.get(pk=n1.id).read)
        # un autre utilisateur ne peut pas marquer mes notifications
        c2 = Client(HTTP_HOST='127.0.0.1'); c2.force_login(self.a)
        c2.post('/notif/read/%d/' % n2.id)
        self.assertFalse(Notification.objects.get(pk=n2.id).read)

        async def scenario():
            comm = self._notif_comm(self.b)
            await comm.connect()
            await comm.send_json_to({'command': 'mark_notification_read', 'notification_id': str(n2.id)})
            cnt = await self._drain(comm, lambda d: d.get('general_msg_type') == 4)
            self.assertEqual(cnt['count'], 0)
            await comm.disconnect()
        asyncio.run(scenario())
        self.assertTrue(Notification.objects.get(pk=n2.id).read)

    def test_stale_presence_cleared_at_startup(self):
        from ZOOT.routing import _reset_chat_presence
        self.room.connected_users.add(self.b)      # « connecté » fantôme (redémarrage)
        _reset_chat_presence()
        self.assertEqual(self.room.connected_users.count(), 0)
