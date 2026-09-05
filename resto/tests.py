"""
Tests de la section Resto : parcours complet client → restaurant → livreur.
Lancer :  python manage.py test resto
"""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Cart, Courier, MenuCategory, MenuItem, Option, OptionGroup, Order, Restaurant

User = get_user_model()


class RestoFlowTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user(email='owner@test.mg', username='owner', password='pass12345')
        self.client_user = User.objects.create_user(email='client@test.mg', username='client', password='pass12345')
        self.courier_user = User.objects.create_user(email='livreur@test.mg', username='livreur', password='pass12345')

        self.resto = Restaurant.objects.create(
            owner=self.owner, name='Hotely Mamy', address='Analakely', region='analamanga',
            delivery_fee=2000, is_approved=True, latitude=-18.91, longitude=47.52,
        )
        self.cat = MenuCategory.objects.create(restaurant=self.resto, name='Plats')
        self.item = MenuItem.objects.create(restaurant=self.resto, category=self.cat, name='Ravitoto', price=8000)
        self.sauce = OptionGroup.objects.create(item=self.item, name='Sauce', min_select=1, max_select=1)
        self.sauce_a = Option.objects.create(group=self.sauce, name='Piment')
        self.sauce_b = Option.objects.create(group=self.sauce, name='Nature')
        self.extras = OptionGroup.objects.create(item=self.item, name='Suppléments', min_select=0, max_select=2)
        self.egg = Option.objects.create(group=self.extras, name='Œuf', extra_price=1000)
        self.rice = Option.objects.create(group=self.extras, name='Riz en plus', extra_price=500)
        self.item.ingredients = 'Oignons' + chr(10) + 'Piment' + chr(10) + '!Riz'
        self.item.preparation = 'Mijoté 2 h'
        self.item.save()

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _add(self, options, quantity=1, replace=False, note='', removed=None):
        return self.client.post(
            reverse('resto:cart_add', args=[self.item.pk]),
            data=json.dumps({'quantity': quantity, 'options': options, 'replace': replace, 'note': note,
                             'removed': removed or []}),
            content_type='application/json',
        )

    def _status(self, order, status, **extra):
        return self.client.post(reverse('resto:order_set_status', args=[order.number]),
                                data=json.dumps({'status': status, **extra}), content_type='application/json')

    # ── Tests ─────────────────────────────────────────────────────────────────
    def test_index_lists_only_approved_restaurants(self):
        Restaurant.objects.create(owner=self.owner, name='Caché', address='x', is_approved=False)
        r = self.client.get(reverse('resto:index'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Hotely Mamy')
        self.assertNotContains(r, 'Caché')

    def test_item_options_json(self):
        r = self.client.get(reverse('resto:item_options', args=[self.resto.slug, self.item.pk]))
        data = r.json()
        self.assertEqual(data['price'], 8000)
        self.assertEqual(data['preparation'], 'Mijoté 2 h')
        self.assertEqual(data['ingredients'], [{'name': 'Oignons', 'removable': True},
                                               {'name': 'Piment', 'removable': True},
                                               {'name': 'Riz', 'removable': False}])
        self.assertEqual([g['name'] for g in data['groups']], ['Sauce', 'Suppléments'])
        self.assertTrue(data['groups'][0]['required'])

    def test_cart_add_validates_required_and_max_options(self):
        self.client.login(email='client@test.mg', password='pass12345')
        # Sauce obligatoire manquante
        r = self._add([])
        self.assertEqual(r.status_code, 400)
        # Trop de suppléments (max 2) — on en met 3 en dupliquant un id invalide + 2 vrais + 1 faux groupe
        third = Option.objects.create(group=self.extras, name='Fromage', extra_price=700)
        r = self._add([self.sauce_a.pk, self.egg.pk, self.rice.pk, third.pk])
        self.assertEqual(r.status_code, 400)
        # OK : sauce + 2 suppléments, quantité 2 → (8000 + 1500) × 2 = 19 000
        r = self._add([self.sauce_a.pk, self.egg.pk, self.rice.pk], quantity=2)
        self.assertEqual(r.status_code, 200, r.content)
        cart = r.json()['cart']
        self.assertEqual(cart['subtotal'], 19000)
        self.assertEqual(cart['total'], 21000)   # + livraison 2 000
        # Même plat + mêmes options → la ligne est incrémentée, pas dupliquée
        self._add([self.sauce_a.pk, self.egg.pk, self.rice.pk])
        self.assertEqual(Cart.objects.get(user=self.client_user).lines.count(), 1)
        self.assertEqual(Cart.objects.get(user=self.client_user).lines.first().quantity, 3)

    def test_removed_ingredients_follow_the_order(self):
        self.client.login(email='client@test.mg', password='pass12345')
        # « Riz » n'est pas retirable : ignoré ; « Oignons » l'est
        r = self._add([self.sauce_a.pk], removed=['Oignons', 'Riz', 'Inconnu'])
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['cart']['lines'][0]['removed'], 'Oignons')
        # Même plat sans rien retirer → ligne distincte
        self._add([self.sauce_a.pk])
        self.assertEqual(Cart.objects.get(user=self.client_user).lines.count(), 2)
        self.client.post(reverse('resto:checkout'), {
            'mode': 'pickup', 'customer_name': 'Tiana', 'customer_phone': '034', 'payment_method': 'cash',
        })
        order = Order.objects.get(customer=self.client_user)
        self.assertEqual(sorted(l.removed_ingredients for l in order.items.all()), ['', 'Oignons'])
        self.assertEqual(int(order.subtotal), 16000)   # le prix ne change pas quand on retire un ingrédient

    def test_cart_is_single_restaurant(self):
        self.client.login(email='client@test.mg', password='pass12345')
        self._add([self.sauce_a.pk])
        other = Restaurant.objects.create(owner=self.owner, name='Autre', address='y', is_approved=True)
        other_item = MenuItem.objects.create(restaurant=other, name='Soupe', price=3000)
        r = self.client.post(reverse('resto:cart_add', args=[other_item.pk]),
                             data=json.dumps({'quantity': 1, 'options': []}), content_type='application/json')
        self.assertEqual(r.status_code, 409)
        r = self.client.post(reverse('resto:cart_add', args=[other_item.pk]),
                             data=json.dumps({'quantity': 1, 'options': [], 'replace': True}), content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Cart.objects.get(user=self.client_user).restaurant, other)

    def test_full_order_and_delivery_flow(self):
        # 1. Le client commande
        self.client.login(email='client@test.mg', password='pass12345')
        self._add([self.sauce_b.pk, self.egg.pk])
        r = self.client.post(reverse('resto:checkout'), {
            'mode': 'delivery', 'customer_name': 'Tiana', 'customer_phone': '+261340000000',
            'delivery_address': 'Ankorondrano, porte bleue', 'delivery_latitude': '-18.88', 'delivery_longitude': '47.52',
            'payment_method': 'cash', 'note': '',
        })
        self.assertEqual(r.status_code, 302)
        order = Order.objects.get(customer=self.client_user)
        self.assertEqual(order.status, Order.STATUS_PENDING)
        self.assertEqual(int(order.subtotal), 9000)
        self.assertEqual(int(order.total), 11000)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().options.count(), 2)
        self.assertEqual(order.pickup_latitude, -18.91)
        self.assertFalse(Cart.objects.filter(user=self.client_user).exists())
        self.assertTrue(order.number.startswith('VZ-'))

        # Le client voit sa commande ; un inconnu non
        self.assertEqual(self.client.get(reverse('resto:order', args=[order.number])).status_code, 200)
        self.assertEqual(self.client.get(reverse('resto:order_state', args=[order.number])).json()['status'], 'pending')
        # Le client ne peut pas faire avancer la commande
        self.assertEqual(self._status(order, 'accepted').status_code, 403)

        # 2. Le restaurant accepte, prépare, marque prête
        self.client.login(email='owner@test.mg', password='pass12345')
        self.assertEqual(self._status(order, 'delivered').status_code, 403)   # transition interdite
        self.assertEqual(self._status(order, 'accepted', estimated_minutes=25).status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.estimated_minutes, 25)
        self.assertIsNotNone(order.accepted_at)
        self._status(order, 'preparing')
        self._status(order, 'ready')
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_READY)

        # 3. Un livreur rattaché prend la commande, partage sa position, livre
        courier = Courier.objects.create(user=self.courier_user, restaurant=self.resto, phone='034', is_approved=True, is_available=True)
        self.client.login(email='livreur@test.mg', password='pass12345')
        r = self.client.get(reverse('resto:courier_dashboard'))
        self.assertContains(r, order.number)
        self.client.post(reverse('resto:courier_take', args=[order.number]))
        order.refresh_from_db()
        self.assertEqual(order.courier, courier)
        self.assertEqual(order.status, Order.STATUS_PICKED_UP)
        self.client.post(reverse('resto:courier_position'), data=json.dumps({'lat': -18.9, 'lng': 47.51}), content_type='application/json')
        self._status(order, 'delivering')
        # Le client voit la position du livreur dans le suivi
        self.client.login(email='client@test.mg', password='pass12345')
        state = self.client.get(reverse('resto:order_state', args=[order.number])).json()
        self.assertEqual(state['status'], 'delivering')
        self.assertEqual(state['courier']['lat'], -18.9)
        self.assertEqual(state['pickup']['name'], 'Hotely Mamy')
        self.assertTrue(any(s['current'] for s in state['steps']))
        # Livraison
        self.client.login(email='livreur@test.mg', password='pass12345')
        self._status(order, 'delivered')
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_DELIVERED)
        self.assertIsNotNone(order.delivered_at)
        # pending, accepted, preparing, ready, picked_up, delivering, delivered
        self.assertEqual(order.events.count(), 7)

    def test_customer_can_cancel_only_before_preparation(self):
        self.client.login(email='client@test.mg', password='pass12345')
        self._add([self.sauce_a.pk])
        self.client.post(reverse('resto:checkout'), {
            'mode': 'pickup', 'customer_name': 'Tiana', 'customer_phone': '034', 'payment_method': 'mvola',
        })
        order = Order.objects.get(customer=self.client_user)
        self.assertEqual(int(order.delivery_fee), 0)          # retrait : pas de frais
        self.client.post(reverse('resto:order_cancel', args=[order.number]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_CANCELLED)

    def test_vendor_menu_and_options_editor(self):
        self.client.login(email='owner@test.mg', password='pass12345')
        r = self.client.post(reverse('resto:item_save', args=[self.resto.slug]),
                             {'name': 'Mofo gasy', 'price': 500, 'order': 0, 'is_available': 'on'})
        self.assertEqual(r.status_code, 302)
        item = MenuItem.objects.get(name='Mofo gasy')
        r = self.client.post(reverse('resto:item_options_save', args=[self.resto.slug, item.pk]),
                             data=json.dumps({'groups': [
                                 {'name': 'Quantité', 'min': 1, 'max': 1, 'options': [{'name': '5 pièces', 'extra_price': 0}, {'name': '10 pièces', 'extra_price': 400}]},
                                 {'name': '', 'min': 0, 'max': 1, 'options': []},   # ignoré
                             ]}), content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(item.option_groups.count(), 1)
        self.assertEqual(item.option_groups.first().options.count(), 2)
        # Un autre utilisateur ne peut pas toucher au menu
        self.client.login(email='client@test.mg', password='pass12345')
        r = self.client.post(reverse('resto:item_delete', args=[self.resto.slug, item.pk]))
        self.assertEqual(r.status_code, 404)

    def test_pages_render(self):
        self.client.login(email='owner@test.mg', password='pass12345')
        for name, args in [('resto:index', []), ('resto:restaurant', [self.resto.slug]), ('resto:cart', []),
                           ('resto:my_orders', []), ('resto:vendor_dashboard', []), ('resto:restaurant_create', []),
                           ('resto:restaurant_edit', [self.resto.slug]), ('resto:menu_manage', [self.resto.slug]),
                           ('resto:vendor_orders', [self.resto.slug]), ('resto:vendor_couriers', [self.resto.slug]),
                           ('resto:courier_signup', [])]:
            r = self.client.get(reverse(name, args=args))
            self.assertEqual(r.status_code, 200, f'{name} → {r.status_code}')
