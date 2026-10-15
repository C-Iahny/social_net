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


class StoryPreUploadTests(TestCase):
    """Envoi du média dès sa sélection, publication par jeton (WebView Android)."""
    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()
        self.me = Account.objects.create_user(email='up@test.mg', username='up', password='pw12345678')
        self.c = Client()
        self.c.force_login(self.me)

    def _png(self):
        import io
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        buf = io.BytesIO(); Image.new('RGB', (40, 30), (200, 30, 30)).save(buf, 'PNG'); buf.seek(0)
        return SimpleUploadedFile('photo.png', buf.read(), content_type='image/png')

    def test_upload_then_publish_with_token(self):
        from django.test import override_settings
        from django.core.cache import cache
        from stories.models import Story
        with override_settings(MEDIA_ROOT=self.tmp):
            r = self.c.post(reverse('stories:upload'), {'media': self._png()})
            self.assertEqual(r.status_code, 200, r.content)
            d = r.json()
            self.assertTrue(d['ok']); self.assertEqual(d['media_type'], 'image'); self.assertIn('tmp_', d['url'])
            token = d['token']
            r = self.c.post(reverse('stories:create'), {'story_type': 'image', 'media_token': token, 'caption': 'Salama', 'text_size': 8})
            self.assertEqual(r.status_code, 200, r.content)
            s = Story.objects.get(pk=r.json()['story']['id'])
            self.assertEqual(s.media_type, 'image')
            self.assertIn('tmp_' + token, s.media.name)
            self.assertIsNone(cache.get('story:tmp:' + token))      # jeton consommé
            # un jeton inconnu est refusé
            r = self.c.post(reverse('stories:create'), {'story_type': 'image', 'media_token': 'abc'})
            self.assertEqual(r.status_code, 400)

    def test_discard_removes_file(self):
        from django.test import override_settings
        from django.core.cache import cache
        from django.core.files.storage import default_storage
        with override_settings(MEDIA_ROOT=self.tmp):
            d = self.c.post(reverse('stories:upload'), {'media': self._png()}).json()
            info = cache.get('story:tmp:' + d['token'])
            self.assertTrue(default_storage.exists(info['name']))
            self.c.post(reverse('stories:upload-discard'), {'token': d['token']})
            self.assertFalse(default_storage.exists(info['name']))
            self.assertIsNone(cache.get('story:tmp:' + d['token']))

    def test_creator_uses_pre_upload(self):
        html = self.c.get(reverse('post:post-view') + '?tab=feed').content.decode()
        self.assertIn('function _zscUploadNow(file)', html)
        self.assertIn("fd.append('media_token', _sc.token)", html)
        self.assertIn('/stories/upload/', html)


class MusicCatalogueTests(TestCase):
    """Catalogue musique : tendances sans saisie, genres, recherche — API Deezer simulée."""
    def setUp(self):
        self.me = Account.objects.create_user(email='mus@test.mg', username='mus', password='pw12345678')
        self.c = Client()
        self.c.force_login(self.me)
        from django.core.cache import cache
        cache.clear()

    def _fake(self, *a, **kw):
        class R:
            status_code = 200
            def raise_for_status(self): pass
            def json(self_inner):
                data = [{'id': 1, 'title': 'E tiako', 'title_short': 'E tiako', 'duration': 329,
                                   'preview': 'https://cdnt-preview.dzcdn.net/x.mp3', 'explicit_lyrics': False,
                                   'artist': {'name': 'Jaojoby'}, 'album': {'cover_medium': 'https://cdn-images.dzcdn.net/c.jpg'}},
                                  {'id': 2, 'title': 'Sans extrait', 'duration': 100, 'preview': '', 'artist': {'name': 'X'}, 'album': {}}]
                return {'data': data, 'tracks': {'data': data}}
        self.calls.append((a, kw))
        return R()

    def test_trending_genre_and_search(self):
        from unittest import mock
        import stories.views as sv
        self.calls = []
        with mock.patch.object(sv.http_requests, 'get', side_effect=self._fake):
            d = self.c.get(reverse('stories:music-search')).json()
            self.assertEqual(len(d['tracks']), 1)                      # le titre sans extrait est écarté
            t = d['tracks'][0]
            self.assertEqual((t['name'], t['artist'], t['duration'], t['full_duration']), ('E tiako', 'Jaojoby', 30, 329))
            self.assertIn('chart/0/tracks', self.calls[-1][0][0])
            self.c.get(reverse('stories:music-search') + '?tag=hiphop')
            self.assertIn('editorial/116/charts', self.calls[-1][0][0])
            self.c.get(reverse('stories:music-search') + '?q=bodo')
            self.assertEqual(self.calls[-1][1]['params']['q'], 'bodo')
            n = len(self.calls)
            self.c.get(reverse('stories:music-search') + '?q=bodo')     # servi depuis le cache
            self.assertEqual(len(self.calls), n)

    def test_requires_login(self):
        r = Client().get(reverse('stories:music-search'))
        self.assertIn(r.status_code, (302, 401, 403))

    def test_deezer_preview_allowed_for_download(self):
        import stories.views as sv
        self.assertEqual(sv._check_audio_url('https://cdnt-preview.dzcdn.net/api/1/x.mp3'), 'https://cdnt-preview.dzcdn.net/api/1/x.mp3')
        with self.assertRaises(ValueError):
            sv._check_audio_url('https://evil.example.com/x.mp3')

    def test_music_sheet_markup(self):
        html = self.c.get(reverse('post:post-view') + '?tab=feed').content.decode()
        for needle in ['id="zsc-music-chips"', 'data-tag="gasy"', 'zscMusicPreview(', 'id="zsc-trim"', 'function _musicLoad()']:
            self.assertIn(needle, html)
        self.assertNotIn('zscAudioTab', html)
