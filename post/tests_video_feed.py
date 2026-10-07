"""Fil vidéo vertical « Pour toi » (post/video_feed.py)."""
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse

from account.models import Account
from friend.models import FriendList
from group.models import Group, GroupMembership
from post.models import Post, PostMedia, Reaction
from post.video_feed import ranked_video_post_ids, video_page


def mk(name):
    return Account.objects.create_user(email='%s@test.mg' % name, username=name, password='pw12345678')


def video_post(author, body='', **kw):
    post = Post.objects.create(author=author, body=body, **kw)
    PostMedia.objects.create(post=post, media_type=PostMedia.VIDEO, order=0,
                             file=SimpleUploadedFile('clip.mp4', b'\x00\x00\x00\x18ftypmp42', content_type='video/mp4'))
    return post


class VideoFeedTests(TestCase):
    def setUp(self):
        cache.clear()
        self.me, self.friend, self.stranger = mk('moi'), mk('ami'), mk('inconnu')
        FriendList.objects.get_or_create(user=self.me)[0].friends.add(self.friend)
        self.client = Client()
        self.client.force_login(self.me)

    def tearDown(self):
        for m in PostMedia.objects.all():
            m.file.delete(save=False)

    def test_only_video_posts_are_listed(self):
        v = video_post(self.stranger, 'une vidéo')
        Post.objects.create(author=self.stranger, body='texte seulement')
        self.assertEqual(ranked_video_post_ids(self.me), [v.id])

    def test_private_group_video_hidden(self):
        private = Group.objects.create(name='Prive', creator=self.stranger, privacy=Group.PRIVATE)
        GroupMembership.objects.create(user=self.stranger, group=private, role=GroupMembership.ADMIN)
        video_post(self.stranger, 'secret', group=private)
        public = video_post(self.stranger, 'public')
        self.assertEqual(ranked_video_post_ids(self.me), [public.id])

    def test_engagement_and_friends_rank_higher(self):
        quiet = video_post(self.stranger, 'calme')
        popular = video_post(self.stranger, 'populaire')
        for u in (self.friend, self.stranger):
            Reaction.objects.create(post=popular, user=u, reaction_type='heart')
        from_friend = video_post(self.friend, "d'un ami")
        ids = ranked_video_post_ids(self.me)
        self.assertEqual(ids[0], popular.id)       # 2 réactions > bonus ami
        self.assertEqual(ids[1], from_friend.id)   # bonus ami > rien
        self.assertEqual(ids[-1], quiet.id)

    def test_page_payload_and_pagination(self):
        posts = [video_post(self.stranger, 'clip %d <b>gras</b> #tag' % i) for i in range(8)]
        items, next_offset = video_page(self.me, 0, limit=6)
        self.assertEqual(len(items), 6)
        self.assertEqual(next_offset, 6)
        item = items[0]
        self.assertIn('video', item)
        self.assertNotIn('<b>', item['caption'])
        self.assertEqual(item['author']['username'], 'inconnu')
        items2, next2 = video_page(self.me, 6, limit=6)
        self.assertEqual(len(items2), 2)
        self.assertIsNone(next2)

    def test_pages_render(self):
        video_post(self.stranger, 'bonjour')
        r = self.client.get(reverse('post:video-feed'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'vf-initial')
        r = self.client.get(reverse('post:video-feed-more') + '?offset=0')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()['items']), 1)

    def test_requires_login(self):
        self.assertEqual(Client().get(reverse('post:video-feed')).status_code, 302)
