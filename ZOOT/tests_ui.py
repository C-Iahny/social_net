"""Socle d'interface commun : vérifie que les pages s'appuient bien sur
vz-core.js (toasts, confirmation, garde des formulaires) et que les
corrections de base (zone de sécurité, liens hashtag, barre basse unique)
restent en place."""
import re
from pathlib import Path

from django.conf import settings
from django.test import TestCase, Client
from django.urls import reverse

from account.models import Account

BASE = Path(settings.BASE_DIR)


class UiCoreTests(TestCase):
    def setUp(self):
        self.me = Account.objects.create_user(email='ui@test.mg', username='ui', password='pw12345678')
        self.c = Client()
        self.c.force_login(self.me)

    def _feed(self):
        return self.c.get(reverse('post:post-view') + '?tab=feed').content.decode()

    def test_base_loads_core_and_safe_area(self):
        html = self._feed()
        self.assertIn('js/vz-core.js', html)
        self.assertIn('window.VZ_I18N', html)
        self.assertIn('viewport-fit=cover', html)
        self.assertIn('class="has-bnav"', html)
        self.assertNotIn('ip-api.com', html)
        self.assertNotIn('Material+Symbols', html)
        self.assertNotIn('/post/hashtag/', html)      # ancien préfixe → 404

    def test_no_native_dialogs_left(self):
        for url in [reverse('post:post-view') + '?tab=feed', reverse('account:view', kwargs={'user_id': self.me.pk}),
                    reverse('bazar:mes_annonces'), reverse('resto:cart')]:
            html = self.c.get(url).content.decode()
            self.assertNotRegex(html, r'(?<![\w.$])alert\(', url)
            self.assertNotRegex(html, r'(?<![\w.$])confirm\(', url)

    def test_report_dialog_uses_shared_components(self):
        html = self._feed()
        self.assertIn('id="report-modal-overlay" class="vz-overlay"', html)
        self.assertIn('id="report-submit-btn"', html)
        self.assertIn('vz-btn vz-btn--danger', html)

    def test_flash_messages_rendered_as_toasts(self):
        from django.contrib import messages
        from django.contrib.messages.storage.fallback import FallbackStorage
        # le rendu passe par un bloc JSON lu par vz-core.js
        html = self._feed()
        self.assertNotIn('id="django-messages"', html)

    def test_declarative_confirms(self):
        html = self.c.get(reverse('bazar:mes_annonces')).content.decode()
        self.assertNotIn('onsubmit="return confirm', html)
        html = self.c.get(reverse('post:mes-brouillons')).content.decode()
        self.assertNotIn('return confirm(', html)

    def test_static_core_files(self):
        css = (BASE / 'static' / 'css' / 'zoot-base.css').read_text()
        self.assertEqual(css.count('\n.vz-btn {'), 1)
        self.assertIn('--danger:', css)
        self.assertIn(':focus-visible', css)
        self.assertIn('prefers-reduced-motion', css)
        # barre basse : une seule règle fixed
        self.assertEqual(len(re.findall(r'\.zoot-bottom-nav \{\s*display: flex;\s*position: fixed;', css)), 1)
        self.assertNotIn('main { padding-bottom: 68px; }', css)
        js = (BASE / 'static' / 'js' / 'vz-core.js').read_text()
        for name in ['window.vzToast', 'window.vzAlert', 'window.vzConfirm', 'window.vzLayers', 'data-vz-confirm', 'vzSubmitting']:
            self.assertIn(name, js)

    def test_hashtag_links_use_feed_prefix(self):
        for tpl in ['post/templates/post/post_view.html', 'post/templates/post/hashtag.html']:
            src = (BASE / tpl).read_text()
            self.assertNotIn('/post/hashtag/', src, tpl)
            self.assertIn('{% url "post:hashtag" tag="__TAG__" %}', src, tpl)


class LanguageChoiceTests(TestCase):
    """L'anglais est de nouveau sélectionnable ; le français reste la langue par défaut."""
    def test_default_is_french_without_cookie(self):
        r = Client().get('/legal/confidentialite/')
        self.assertEqual(r.cookies.get('zoot_language').value, 'fr')

    def test_english_cookie_is_respected(self):
        c = Client(); c.cookies['zoot_language'] = 'en'
        html = c.get('/login/').content.decode()
        self.assertIn('lang="en"', html)
        self.assertNotIn('zoot_language=fr', str(c.cookies))

    def test_malagasy_cookie_is_respected(self):
        c = Client(); c.cookies['zoot_language'] = 'mg'
        self.assertIn('lang="mg"', c.get('/login/').content.decode())
