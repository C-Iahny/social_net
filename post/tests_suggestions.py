"""Suggestions de profils du fil d'actualité (carrousel horizontal)."""

from django.test import TestCase, Client
from django.urls import reverse

from account.models import Account
from friend.models import FriendList, FriendRequest
from post.models import Post
from post.views import get_profile_suggestions


def mk(name):
    return Account.objects.create_user(
        email='%s@test.mg' % name, username=name, password='pw12345678',
    )


class ProfileSuggestionTests(TestCase):
    def setUp(self):
        self.me       = mk('me')
        self.friend   = mk('afriend')
        self.fof      = mk('friendoffriend')
        self.pending  = mk('pendinguser')
        self.stranger = mk('stranger')

        # La FriendList est créée par un signal à la création du compte.
        FriendList.objects.get_or_create(user=self.me)[0].friends.add(self.friend)
        FriendList.objects.get_or_create(user=self.friend)[0].friends.set([self.me, self.fof])
        FriendList.objects.get_or_create(user=self.fof)[0].friends.add(self.friend)
        FriendRequest.objects.create(sender=self.me, receiver=self.pending)

    def _feed_html(self):
        client = Client()
        client.force_login(self.me)
        response = client.get(reverse('post:post-view'))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_excludes_self_friends_and_pending_requests(self):
        names = [a.username for a in get_profile_suggestions(self.me)]
        self.assertNotIn('me', names)
        self.assertNotIn('afriend', names)
        self.assertNotIn('pendinguser', names)

    def test_friend_of_friend_ranked_first_with_mutual_count(self):
        suggestions = get_profile_suggestions(self.me)
        self.assertEqual(suggestions[0].username, 'friendoffriend')
        self.assertEqual(suggestions[0].mutuals, 1)
        # Le reste de la liste est complété avec les autres comptes
        self.assertIn('stranger', [a.username for a in suggestions])
        self.assertTrue(all(hasattr(a, 'region_label') for a in suggestions))

    def test_carousel_rendered_on_empty_feed(self):
        html = self._feed_html()
        self.assertIn('id="sugg-scroller"', html)
        self.assertIn('friendoffriend', html)

    def test_carousel_inserted_once_after_second_post(self):
        for i in range(4):
            Post.objects.create(author=self.me, title='p%d' % i, body='hello %d' % i)
        html = self._feed_html()
        self.assertEqual(html.count('id="sugg-scroller"'), 1)
        second_post = Post.objects.order_by('-id')[1]
        self.assertLess(html.index('post-%d' % second_post.id),
                        html.index('id="sugg-scroller"'))

    def test_carousel_rendered_when_feed_has_a_single_post(self):
        Post.objects.create(author=self.me, title='solo', body='x')
        html = self._feed_html()
        self.assertEqual(html.count('id="sugg-scroller"'), 1)
