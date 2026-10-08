"""Achat depuis un post / une vidéo : lien vers une annonce Bazar ou un plat Resto."""
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse

from account.models import Account
from bazar.models import Annonce
from post.models import Post, PostMedia
from post.products import attach_products, user_products
from post.video_feed import video_page
from resto.models import Restaurant, MenuItem


def mk(name):
    return Account.objects.create_user(email='%s@test.mg' % name, username=name, password='pw12345678')


class ProductLinkTests(TestCase):
    def setUp(self):
        cache.clear()
        self.seller, self.other = mk('vendeur'), mk('client')
        self.annonce = Annonce.objects.create(seller=self.seller, title='Vélo Peugeot', price=250000,
                                              category='sports', condition='bon')
        self.foreign = Annonce.objects.create(seller=self.other, title='Pas à moi', price=1000,
                                              category='autres', condition='bon')
        self.resto = Restaurant.objects.create(owner=self.seller, name='Hotely Soa',
                                               is_approved=True, is_active=True, is_open=True)
        self.plat = MenuItem.objects.create(restaurant=self.resto, name='Ravitoto', price=6000)
        self.c = Client()
        self.c.force_login(self.seller)

    def tearDown(self):
        for m in PostMedia.objects.all():
            m.file.delete(save=False)

    def _add(self, product):
        return self.c.post(reverse('post:addPost'),
                           {'title': 'À vendre', 'body': 'super', 'product': product, 'ajax': '1'})

    def test_link_own_annonce(self):
        r = self._add('bazar:%d' % self.annonce.pk)
        self.assertEqual(r.status_code, 200)
        post = Post.objects.get(pk=r.json()['post_id'])
        self.assertEqual(post.annonce_id, self.annonce.pk)
        self.assertIsNone(post.menu_item_id)
        html = r.json()['html']
        self.assertIn('pc-product', html)
        self.assertIn('Vélo Peugeot', html)
        self.assertIn('250 000 Ar', html)
        self.assertIn(reverse('bazar:detail', args=[self.annonce.pk]), html)

    def test_cannot_link_someone_elses_annonce(self):
        r = self._add('bazar:%d' % self.foreign.pk)
        post = Post.objects.get(pk=r.json()['post_id'])
        self.assertIsNone(post.annonce_id)
        self.assertNotIn('pc-product', r.json()['html'])

    def test_link_own_dish_points_to_restaurant_page(self):
        r = self._add('resto:%d' % self.plat.pk)
        post = Post.objects.get(pk=r.json()['post_id'])
        self.assertEqual(post.menu_item_id, self.plat.pk)
        html = r.json()['html']
        self.assertIn('Ravitoto', html)
        self.assertIn(reverse('resto:restaurant', args=[self.resto.slug]) + '?plat=%d' % self.plat.pk, html)
        self.assertIn('Commander', html)

    def test_sold_annonce_is_marked_unavailable(self):
        self.annonce.status = 'vendue'
        self.annonce.save()
        post = Post.objects.create(author=self.seller, body='x', annonce=self.annonce)
        attach_products([post])
        self.assertFalse(post.product['available'])
        html = self.c.get(reverse('post:post-detail', args=[post.pk])).content.decode()
        self.assertIn('Indisponible', html)

    def test_my_products_lists_only_mine(self):
        refs = {p['ref'] for p in user_products(self.seller)}
        self.assertEqual(refs, {'bazar:%d' % self.annonce.pk, 'resto:%d' % self.plat.pk})
        data = self.c.get(reverse('post:my-products')).json()
        self.assertEqual({p['ref'] for p in data['products']}, refs)

    def test_update_can_clear_product(self):
        post = Post.objects.create(author=self.seller, title='t', body='x', annonce=self.annonce)
        self.c.post(reverse('post:edit-post', args=[post.pk]), {'title': 't', 'body': 'x', 'product': ''})
        post.refresh_from_db()
        self.assertIsNone(post.annonce_id)

    def test_video_feed_item_carries_product(self):
        post = Post.objects.create(author=self.seller, body='clip', annonce=self.annonce)
        PostMedia.objects.create(post=post, media_type=PostMedia.VIDEO, order=0,
                                 file=SimpleUploadedFile('clip.mp4', b'\x00\x00\x00\x18ftypmp42', content_type='video/mp4'))
        items, _ = video_page(self.other, 0)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['product']['title'], 'Vélo Peugeot')
        self.assertEqual(items[0]['product']['cta'], 'Acheter')

    def test_forms_render_picker(self):
        r = self.c.get(reverse('post:addPost') + '?video=1')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('pp-open-btn', html)
        self.assertIn('video-hint', html)
        post = Post.objects.create(author=self.seller, title='t', body='x', menu_item=self.plat)
        html = self.c.get(reverse('post:edit-post', args=[post.pk])).content.decode()
        self.assertIn('value="resto:%d"' % self.plat.pk, html)
