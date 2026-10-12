"""Conformité : blocage d'utilisateur, suppression de compte, signalement
étendu, politique de confidentialité unique."""
import json
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, Client
from django.urls import reverse

from account.models import Account, UserBlock
from post.models import Post, Comment, Report


class BlockTests(TestCase):
    def setUp(self):
        self.me = Account.objects.create_user(email='me@test.mg', username='me', password='pw12345678')
        self.other = Account.objects.create_user(email='other@test.mg', username='other', password='pw12345678')
        self.c = Client(); self.c.force_login(self.me)
        Post.objects.create(author=self.other, title='hello', body='visible')

    def test_toggle_block_and_hide_posts(self):
        url = reverse('account:block', kwargs={'user_id': self.other.pk})
        r = self.c.post(url)
        self.assertEqual(r.json(), {'ok': True, 'blocked': True})
        self.assertTrue(UserBlock.objects.filter(blocker=self.me, blocked=self.other).exists())
        # Explorer ne montre plus les posts du bloqué
        html = self.c.get(reverse('post:index')).content.decode()
        self.assertNotIn('>hello<', html)
        # et inversement, le bloqué ne voit plus les miens
        Post.objects.create(author=self.me, title='mine-title', body='x')
        c2 = Client(); c2.force_login(self.other)
        self.assertNotIn('mine-title', c2.get(reverse('post:index')).content.decode())
        # débloquer
        r = self.c.post(url)
        self.assertEqual(r.json(), {'ok': True, 'blocked': False})

    def test_block_prevents_chat_and_friend_request(self):
        UserBlock.objects.create(blocker=self.other, blocked=self.me)
        r = self.c.post(reverse('chat:create-or-return-private-chat'), {'user2_id': self.other.pk})
        self.assertEqual(r.status_code, 403)
        r = self.c.post(reverse('friend:friend-request'), {'receiver_user_id': self.other.pk})
        self.assertEqual(r.status_code, 403)

    def test_profile_shows_block_button_and_settings_list(self):
        html = self.c.get(reverse('account:view', kwargs={'user_id': self.other.pk})).content.decode()
        self.assertIn('id="profile-block-btn"', html)
        UserBlock.objects.create(blocker=self.me, blocked=self.other)
        html = self.c.get(reverse('account:edit', kwargs={'user_id': self.me.pk})).content.decode()
        self.assertIn('blocked-row-%d' % self.other.pk, html)
        self.assertIn(reverse('account:delete'), html)


class DeleteAccountTests(TestCase):
    def setUp(self):
        self.me = Account.objects.create_user(email='bye@test.mg', username='bye', password='pw12345678')
        self.c = Client(); self.c.force_login(self.me)

    def test_requires_login(self):
        r = Client().get(reverse('account:delete'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login/', r['Location'])

    def test_wrong_password(self):
        r = self.c.post(reverse('account:delete'), {'password': 'nope'})
        self.assertEqual(r.status_code, 200)
        self.assertIn('Mot de passe incorrect', r.content.decode())
        self.assertTrue(Account.objects.filter(pk=self.me.pk).exists())

    def test_delete(self):
        Post.objects.create(author=self.me, title='t', body='b')
        r = self.c.post(reverse('account:delete'), {'password': 'pw12345678'})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Account.objects.filter(pk=self.me.pk).exists())
        self.assertFalse(Post.objects.filter(title='t').exists())


class ReportAndPrivacyTests(TestCase):
    def setUp(self):
        self.me = Account.objects.create_user(email='rep@test.mg', username='rep', password='pw12345678')
        self.other = Account.objects.create_user(email='auth@test.mg', username='auth', password='pw12345678')
        self.c = Client(); self.c.force_login(self.me)

    def test_report_comment_and_group_types(self):
        p = Post.objects.create(author=self.other, title='t', body='b')
        cmt = Comment.objects.create(post=p, author=self.other, body='mechant')
        r = self.c.post(reverse('post:report-content'), {'ct': 'comment', 'object_id': cmt.pk, 'reason': 'hate'})
        self.assertEqual(r.json(), {'ok': True})
        self.assertEqual(Report.objects.filter(content_type=ContentType.objects.get_for_model(Comment), object_id=cmt.pk).count(), 1)
        r = self.c.post(reverse('post:report-content'), {'ct': 'restaurant', 'object_id': 1, 'reason': 'spam'})
        self.assertEqual(r.json(), {'ok': True})
        r = self.c.post(reverse('post:report-content'), {'ct': 'nimporte', 'object_id': 1})
        self.assertEqual(r.status_code, 400)

    def test_comment_report_button_rendered(self):
        p = Post.objects.create(author=self.other, title='t', body='b')
        Comment.objects.create(post=p, author=self.other, body='x')
        html = self.c.get('/feed/%d/' % p.pk).content.decode()
        self.assertIn("openReportModal('comment'", html)

    def test_privacy_redirects_to_single_page(self):
        r = Client().get('/privacy/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], reverse('legal:confidentialite'))
        html = Client().get(reverse('legal:confidentialite')).content.decode()
        self.assertIn('/account/supprimer/', html)
