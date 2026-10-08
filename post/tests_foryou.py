"""Onglet « Pour toi » du fil principal (post/foryou.py) et pagination par onglet."""
from django.core.cache import cache
from django.test import TestCase, Client
from django.urls import reverse

from account.models import Account
from friend.models import FriendList
from group.models import Group, GroupMembership
from post.models import Post, Reaction
from post.foryou import ranked_feed_post_ids


def mk(name, **kw):
    return Account.objects.create_user(email='%s@test.mg' % name, username=name, password='pw12345678', **kw)


class ForYouTests(TestCase):
    def setUp(self):
        cache.clear()
        self.me = mk('moi')
        self.friend = mk('ami')
        self.stranger = mk('inconnu')
        self.c = Client()
        self.c.force_login(self.me)

    def test_ranking_excludes_own_hidden_and_private_posts(self):
        mine = Post.objects.create(author=self.me, body='moi')
        draft = Post.objects.create(author=self.stranger, body='brouillon', status=Post.STATUS_DRAFT)
        g = Group.objects.create(name='Secret', creator=self.stranger, privacy=Group.PRIVATE)
        GroupMembership.objects.create(user=self.stranger, group=g, role=GroupMembership.ADMIN)
        private = Post.objects.create(author=self.stranger, body='prive', group=g)
        public = Post.objects.create(author=self.stranger, body='public')
        ids = ranked_feed_post_ids(self.me)
        self.assertIn(public.id, ids)
        for p in (mine, draft, private):
            self.assertNotIn(p.id, ids)

    def test_engagement_and_friends_rank_higher(self):
        quiet = Post.objects.create(author=self.stranger, body='calme')
        popular = Post.objects.create(author=self.stranger, body='populaire')
        for u in (self.friend, mk('x1'), mk('x2')):
            Reaction.objects.create(post=popular, user=u, reaction_type='like')
        FriendList.objects.get_or_create(user=self.me)[0].friends.add(self.friend)
        from_friend = Post.objects.create(author=self.friend, body='ami')
        ids = ranked_feed_post_ids(self.me)
        self.assertLess(ids.index(popular.id), ids.index(quiet.id))
        self.assertLess(ids.index(from_friend.id), ids.index(quiet.id))

    def test_new_user_without_friends_lands_on_foryou(self):
        Post.objects.create(author=self.stranger, body='bienvenue')
        r = self.c.get(reverse('post:post-view'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['active_tab'], 'foryou')
        self.assertIn('bienvenue', r.content.decode())

    def test_user_with_friends_lands_on_own_feed(self):
        FriendList.objects.get_or_create(user=self.me)[0].friends.add(self.friend)
        r = self.c.get(reverse('post:post-view'))
        self.assertEqual(r.context['active_tab'], 'feed')

    def test_feed_more_respects_tab_and_visibility(self):
        for i in range(7):
            Post.objects.create(author=self.stranger, body='reco %d' % i)
        Post.objects.create(author=self.stranger, body='cache', status=Post.STATUS_DRAFT)
        r = self.c.get(reverse('post:feed-more') + '?page=2&tab=foryou', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        data = r.json()
        self.assertIn('reco', data['html'])
        self.assertNotIn('cache', data['html'])
        self.assertFalse(data['has_next'])
        # l'onglet amis, lui, ne montre pas les inconnus
        r = self.c.get(reverse('post:feed-more') + '?page=1&tab=feed', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertNotIn('reco', r.json()['html'])
