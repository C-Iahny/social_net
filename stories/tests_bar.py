"""Barre des stories : accroches JS attendues par le fil et la page profil."""
from django.test import TestCase, Client
from django.urls import reverse

from account.models import Account


class StoryBarHooksTests(TestCase):
    def setUp(self):
        self.me = Account.objects.create_user(email='moi@test.mg', username='moi', password='pw12345678')
        self.other = Account.objects.create_user(email='lui@test.mg', username='lui', password='pw12345678')
        self.c = Client()
        self.c.force_login(self.me)

    def test_feed_exposes_viewer_hooks(self):
        html = self.c.get(reverse('post:post-view') + '?tab=feed').content.decode()
        # Le widget latéral appelle openStoryViewer / zootStories.groups() et écoute l'événement
        self.assertIn('window.openStoryViewer = function', html)
        self.assertIn('groups: function(){ return _sv.groups; }', html)
        self.assertIn("new CustomEvent('zootStoriesLoaded'", html)
        # Feuille « déjà vue » : revoir ou voir la photo de profil
        self.assertIn('window.zsTapGroup = function', html)
        self.assertIn('Revoir la story', html)
        self.assertIn('Voir la photo de profil', html)

    def test_profile_ring_uses_group_chooser(self):
        html = self.c.get(reverse('account:view', kwargs={'user_id': self.other.pk})).content.decode()
        self.assertIn('id="zsv"', html)                      # le viewer est bien présent sur le profil
        self.assertIn('window.zsTapGroup(gi)', html)         # clic sur l'anneau → feuille ou lecture
        self.assertIn('has_unseen: stories.some', html)

    def test_theme_toggle_has_no_blocking_overlay(self):
        html = self.c.get(reverse('post:post-view') + '?tab=feed').content.decode()
        self.assertNotIn('z-index:2147483647', html)
        self.assertIn('function toggleTheme()', html)
        self.assertIn('_syncThemeColor(next)', html)
        # Menu profil mobile : le bouton ferme le menu (et lève le verrou de défilement) lui-même
        self.assertIn('onclick="_vzb_closeDropdown(this); toggleTheme();"', html)
        # le filet de sécurité du verrou de défilement vit dans un script statique
        from pathlib import Path
        from django.conf import settings
        js = ''.join(p.read_text() for p in (Path(settings.BASE_DIR) / 'static' / 'js').glob('vz-*.js'))
        self.assertIn('function _unlockIfNoMenu()', js + html)


class StoryCreatorStyleTests(TestCase):
    """Le texte posé sur une photo est conservé avec son style et renvoyé au lecteur."""
    def setUp(self):
        self.me = Account.objects.create_user(email='crea@test.mg', username='crea', password='pw12345678')
        self.c = Client()
        self.c.force_login(self.me)

    def test_text_story_keeps_style(self):
        r = self.c.post(reverse('stories:create'), {
            'story_type': 'text', 'caption': 'Salama', 'bg_gradient': 'grad_gold',
            'text_color': '#111111', 'text_x': 30, 'text_y': 70, 'text_size': 9.5,
            'text_align': 'left', 'text_bg': 'solid', 'media_fit': 'cover',
        })
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertTrue(data['ok'])
        s = data['story']
        self.assertEqual((s['caption'], s['text_size'], s['text_bg'], s['text_align'], s['media_fit']),
                         ('Salama', 9.5, 'solid', 'left', 'cover'))
        feed = self.c.get(reverse('stories:feed')).json()
        groups = feed['groups'] if isinstance(feed, dict) else feed
        st = groups[0]['stories'][0]
        self.assertEqual(st['text_bg'], 'solid')
        self.assertEqual(st['text_x'], 30.0)

    def test_invalid_style_values_fall_back(self):
        r = self.c.post(reverse('stories:create'), {
            'story_type': 'text', 'caption': 'x', 'text_bg': 'rainbow', 'media_fit': 'zoom',
            'text_size': 'abc', 'text_align': 'diagonal',
        })
        s = r.json()['story']
        self.assertEqual((s['text_bg'], s['media_fit'], s['text_size'], s['text_align']), ('none', 'contain', 0, 'center'))

    def test_creator_markup_present(self):
        html = self.c.get(reverse('post:post-view') + '?tab=feed').content.decode()
        for needle in ['id="zsc-start"', 'id="zsc-canvas"', 'zst-text', 'zscEditText()', 'id="zsc-trash"', 'window.zscPublish = function']:
            self.assertIn(needle, html)
        self.assertNotIn('zscToggleTextMode', html)
