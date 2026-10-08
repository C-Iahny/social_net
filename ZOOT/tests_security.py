"""Contrôles d'accès et protections ajoutés lors de l'audit de sécurité."""

from django.core.cache import cache
from django.test import TestCase, Client, override_settings
from django.urls import reverse

from account.models import Account
from chat.models import PrivateChatRoom, RoomChatMessage
from group.models import Group, GroupMembership, GroupJoinRequest
from post.models import Post
from video.models import LiveRoom


def mk(name):
    return Account.objects.create_user(
        email='%s@test.mg' % name, username=name, password='pw12345678',
    )


def client_for(user):
    c = Client()
    c.force_login(user)
    return c


class PostVisibilityTests(TestCase):
    def setUp(self):
        self.author = mk('author')
        self.other = mk('other')
        self.private = Group.objects.create(name='Secret', creator=self.author, privacy=Group.PRIVATE)
        GroupMembership.objects.create(user=self.author, group=self.private, role=GroupMembership.ADMIN)
        self.draft = Post.objects.create(author=self.author, body='brouillon', status=Post.STATUS_DRAFT)
        self.in_private = Post.objects.create(author=self.author, body='entre nous', group=self.private)
        self.public = Post.objects.create(author=self.author, body='bonjour')

    def test_draft_and_private_group_post_hidden_from_others(self):
        c = client_for(self.other)
        for post in (self.draft, self.in_private):
            self.assertEqual(c.get(reverse('post:post-detail', args=[post.pk])).status_code, 404)
            self.assertEqual(c.get(reverse('post:reactions-who', args=[post.pk])).status_code, 404)
            r = c.post(reverse('post:add-comment', args=[post.pk]), {'body': 'x'})
            self.assertEqual(r.status_code, 404)

    def test_author_still_sees_own_draft(self):
        c = client_for(self.author)
        self.assertEqual(c.get(reverse('post:post-detail', args=[self.draft.pk])).status_code, 200)

    def test_public_post_visible(self):
        c = client_for(self.other)
        self.assertEqual(c.get(reverse('post:post-detail', args=[self.public.pk])).status_code, 200)

    def test_reactions_who_requires_login(self):
        r = Client().get(reverse('post:reactions-who', args=[self.public.pk]))
        self.assertEqual(r.status_code, 302)

    def test_post_body_is_sanitized_in_feed(self):
        Post.objects.create(author=self.other, body='<p>ok</p><script>alert(1)</script>')
        html = client_for(self.other).get(reverse('post:post-view') + '?tab=feed').content.decode()
        self.assertIn('<p>ok</p>', html)
        self.assertNotIn('<script>alert(1)</script>', html)


class PrivateGroupJoinTests(TestCase):
    def setUp(self):
        self.admin = mk('admin1')
        self.outsider = mk('outsider')
        self.group = Group.objects.create(name='Prive', creator=self.admin, privacy=Group.PRIVATE)
        GroupMembership.objects.create(user=self.admin, group=self.group, role=GroupMembership.ADMIN)

    def test_join_private_group_creates_request_not_membership(self):
        client_for(self.outsider).post(reverse('group:join', args=[self.group.slug]))
        self.assertFalse(GroupMembership.objects.filter(user=self.outsider, group=self.group).exists())
        self.assertTrue(GroupJoinRequest.objects.filter(user=self.outsider, group=self.group).exists())

    def test_moderator_accepts_request(self):
        jr = GroupJoinRequest.objects.create(user=self.outsider, group=self.group)
        client_for(self.admin).post(
            reverse('group:join-request-decide', args=[self.group.slug, jr.pk]), {'decision': 'accept'})
        self.assertTrue(GroupMembership.objects.filter(user=self.outsider, group=self.group).exists())
        self.assertFalse(GroupJoinRequest.objects.filter(pk=jr.pk).exists())

    def test_non_moderator_cannot_accept(self):
        jr = GroupJoinRequest.objects.create(user=self.outsider, group=self.group)
        r = client_for(self.outsider).post(
            reverse('group:join-request-decide', args=[self.group.slug, jr.pk]), {'decision': 'accept'})
        self.assertEqual(r.status_code, 403)
        self.assertFalse(GroupMembership.objects.filter(user=self.outsider, group=self.group).exists())

    def test_join_public_group_is_immediate(self):
        public = Group.objects.create(name='Ouvert', creator=self.admin)
        client_for(self.outsider).post(reverse('group:join', args=[public.slug]))
        self.assertTrue(GroupMembership.objects.filter(user=self.outsider, group=public).exists())


class PrivateLiveTests(TestCase):
    def setUp(self):
        self.host = mk('host')
        self.outsider = mk('viewer')
        group = Group.objects.create(name='Live prive', creator=self.host, privacy=Group.PRIVATE)
        GroupMembership.objects.create(user=self.host, group=group, role=GroupMembership.ADMIN)
        self.room = LiveRoom.objects.create(host=self.host, title='Direct', group=group)

    def test_outsider_cannot_open_private_live(self):
        r = client_for(self.outsider).get(reverse('video:live-room', args=[self.room.pk]))
        self.assertEqual(r.status_code, 404)

    def test_private_live_hidden_from_active_list(self):
        data = client_for(self.outsider).get(reverse('video:live-api-active')).json()
        self.assertEqual(data['lives'], [])
        data = client_for(self.host).get(reverse('video:live-api-active')).json()
        self.assertEqual(len(data['lives']), 1)


class ChatAccessTests(TestCase):
    def setUp(self):
        self.a, self.b, self.intruder = mk('alice'), mk('bob'), mk('mallory')
        self.room = PrivateChatRoom.objects.create(user1=self.a, user2=self.b)
        RoomChatMessage.objects.create(user=self.a, room=self.room, content='secret')

    def test_intruder_cannot_open_room(self):
        r = client_for(self.intruder).get(reverse('chat:private-chat-room') + f'?room_id={self.room.pk}')
        self.assertNotIn('secret', r.content.decode())
        self.assertIsNone(r.context.get('room'))

    def test_html_upload_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile('page.html', b'<script>alert(1)</script>', content_type='text/html')
        r = client_for(self.a).post(reverse('chat:upload-chat-file'), {'room_id': self.room.pk, 'file': f})
        self.assertEqual(r.status_code, 400)


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class RateLimitTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_login_blocked_after_too_many_attempts(self):
        c = Client()
        codes = [c.post(reverse('login'), {'email': 'x@test.mg', 'password': 'faux'}).status_code
                 for _ in range(11)]
        self.assertNotIn(429, codes[:10])
        self.assertEqual(codes[10], 429)
