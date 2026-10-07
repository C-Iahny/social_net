"""Commentaires en direct : diffusion WebSocket vers les lecteurs d'un post."""
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase

from account.models import Account
from group.models import Group, GroupMembership
from post.models import Post, Comment
from post.views import _broadcast_comment


def mk(name):
    return Account.objects.create_user(email='%s@test.mg' % name, username=name, password='pw12345678')


class BroadcastCommentTests(TransactionTestCase):
    def test_comment_reaches_post_group(self):
        author, reader = mk('auteur'), mk('lecteur')
        post = Post.objects.create(author=author, body='bonjour')
        comment = Comment.objects.create(post=post, author=reader, body='salut !')
        layer = get_channel_layer()

        async def subscribe():
            channel = await layer.new_channel()
            await layer.group_add(f"post_{post.id}", channel)
            return channel

        async def receive(channel):
            import asyncio
            return await asyncio.wait_for(layer.receive(channel), timeout=2)

        channel = async_to_sync(subscribe)()
        _broadcast_comment(post, comment)   # code synchrone, comme dans la vue
        event = async_to_sync(receive)(channel)
        self.assertEqual(event['type'], 'post_comment')
        self.assertEqual(event['comment']['body'], 'salut !')
        self.assertEqual(event['comment']['post_author_id'], author.id)


class SubscribePostConsumerTests(TransactionTestCase):
    def _connect(self, user):
        from notification.consumers import NotificationConsumer
        communicator = WebsocketCommunicator(NotificationConsumer.as_asgi(), '/')
        communicator.scope['user'] = user
        return communicator

    def test_subscriber_receives_comment(self):
        author, reader = mk('auteur2'), mk('lecteur2')
        post = Post.objects.create(author=author, body='bonjour')

        async def run():
            comm = self._connect(reader)
            connected, _ = await comm.connect()
            assert connected
            await comm.send_json_to({'command': 'subscribe_post', 'post_id': str(post.id)})
            # Le consumer traite les commandes dans l'ordre : attendre la réponse
            # d'une commande suivante garantit que l'abonnement est en place.
            await comm.send_json_to({'command': 'get_unread_general_notifications_count'})
            await comm.receive_json_from()
            await get_channel_layer().group_send(f"post_{post.id}", {
                'type': 'post_comment', 'post_id': post.id, 'comment': {'id': 1, 'body': 'hey'}})
            msg = await comm.receive_json_from()
            await comm.disconnect()
            return msg

        msg = async_to_sync(run)()
        self.assertEqual(msg['general_msg_type'], 8)
        self.assertEqual(msg['comment']['body'], 'hey')

    def test_cannot_subscribe_to_private_group_post(self):
        author, outsider = mk('auteur3'), mk('intrus')
        private = Group.objects.create(name='Prive', creator=author, privacy=Group.PRIVATE)
        GroupMembership.objects.create(user=author, group=private, role=GroupMembership.ADMIN)
        post = Post.objects.create(author=author, body='secret', group=private)

        async def run():
            comm = self._connect(outsider)
            await comm.connect()
            await comm.send_json_to({'command': 'subscribe_post', 'post_id': post.id})
            await get_channel_layer().group_send(f"post_{post.id}", {
                'type': 'post_comment', 'post_id': post.id, 'comment': {'id': 1, 'body': 'hey'}})
            nothing = await comm.receive_nothing(timeout=0.3)
            await comm.disconnect()
            return nothing

        self.assertTrue(async_to_sync(run)())
