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
        self.assertIn('function _unlockIfNoMenu()', html)
