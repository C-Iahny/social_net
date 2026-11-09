"""
Modernisation 2026-11 : dates relatives, carte de post unique, masquage.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Post, PostHide
from .templatetags.vz_tags import relative_label, vz_ariary, vz_since

User = get_user_model()

STATIC = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


class RelativeTimeTests(TestCase):
    def test_labels(self):
        now = timezone.now()
        self.assertEqual(relative_label(now - timedelta(seconds=10), now), "à l'instant")
        self.assertEqual(relative_label(now - timedelta(minutes=5), now), '5 min')
        self.assertEqual(relative_label(now - timedelta(hours=3), now), '3 h')
        self.assertEqual(relative_label(now - timedelta(days=2), now), '2 j')
        self.assertIn(str((now - timedelta(days=400)).year), relative_label(now - timedelta(days=400), now))

    def test_date_objects_and_garbage(self):
        self.assertEqual(relative_label(None), '')
        self.assertEqual(relative_label('nope'), '')
        self.assertTrue(relative_label(timezone.localdate()))

    def test_time_tag_markup(self):
        html = str(vz_since(timezone.now()))
        self.assertIn('<time class="vz-time"', html)
        self.assertIn('data-vz-since', html)

    def test_ariary(self):
        self.assertEqual(vz_ariary(12500), '12 500 Ar')
        self.assertEqual(vz_ariary('abc'), '')


@override_settings(STORAGES=STATIC)
class UnifiedCardTests(TestCase):
    def setUp(self):
        # Le classement « Pour toi » est mis en cache par pk utilisateur ; les pk
        # se répètent d'un test à l'autre, on repart donc d'un cache vide.
        from django.core.cache import cache
        cache.clear()
        self.me = User.objects.create_user(email='me@test.mg', username='me', password='x')
        self.other = User.objects.create_user(email='o@test.mg', username='other', password='x')
        self.client.force_login(self.me)
        for i in range(7):
            Post.objects.create(author=self.other, title='t%d' % i, body='b', status='published')

    def test_created_at_filled_and_relative(self):
        p = Post.objects.first()
        self.assertIsNotNone(p.created_at)
        r = self.client.get('/feed/?tab=foryou')
        self.assertContains(r, 'data-vz-since')
        self.assertNotContains(r, 'date:"d M Y"')

    def test_second_page_has_same_actions_as_first(self):
        first = self.client.get('/feed/?tab=foryou').content.decode()
        more = self.client.get('/feed/feed/more/?page=2&tab=foryou',
                               HTTP_X_REQUESTED_WITH='XMLHttpRequest').json()['html']
        for marker in ('pc-more-btn', 'bk-btn-', 'vzShare(', 'vzPostBookmark('):
            self.assertIn(marker, first, marker)
            self.assertIn(marker, more, marker)
        self.assertNotIn('{#', more)
        self.assertNotIn('{%', more)

    def test_hide_and_undo(self):
        p = Post.objects.first()
        r = self.client.post('/feed/hide/', {'post_id': p.id})
        self.assertEqual(r.json(), {'ok': True, 'hidden': True})
        self.assertTrue(PostHide.objects.filter(user=self.me, post=p).exists())
        html = self.client.get('/feed/?tab=foryou').content.decode()
        self.assertNotIn('id="post-%d"' % p.id, html)
        # le détail direct reste 404 tant que le post est masqué
        self.assertEqual(self.client.get('/feed/%d/' % p.id).status_code, 404)
        r = self.client.post('/feed/hide/', {'post_id': p.id, 'undo': '1'})
        self.assertEqual(r.json(), {'ok': True, 'hidden': False})
        self.assertEqual(self.client.get('/feed/%d/' % p.id).status_code, 200)

    def test_cannot_hide_own_post(self):
        mine = Post.objects.create(author=self.me, title='m', body='b', status='published')
        r = self.client.post('/feed/hide/', {'post_id': mine.id})
        self.assertEqual(r.status_code, 400)

    def test_segmented_tabs_without_inline_hex(self):
        html = self.client.get('/feed/').content.decode()
        self.assertIn('vz-segmented', html)
        self.assertNotIn('#6366f1', html)
        self.assertNotIn('--card-bg', html)


class HashtagAccentTests(TestCase):
    """Un hashtag accentué ne doit plus faire planter le fil ni sa page."""

    def test_accented_hashtag_renders_in_feed_and_resolves(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse
        from .models import Post
        User = get_user_model()
        u = User.objects.create_user(email='acc@test.mg', username='accent', password='x12345678')
        Post.objects.create(author=u, title='Sortie', body='Belle #randonnée à Andasibe', status='published')
        self.client.force_login(u)
        r = self.client.get(reverse('post:post-view'), HTTP_HOST='127.0.0.1')
        self.assertEqual(r.status_code, 200)
        url = reverse('post:hashtag', args=['randonnée'])
        r = self.client.get(url, HTTP_HOST='127.0.0.1')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'randonnée')

