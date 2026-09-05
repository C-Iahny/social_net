"""
resto/views.py — Section « Resto » : restaurants, menus à options, panier,
commandes et suivi de livraison.

Trois rôles, trois espaces :
    /resto/            client   : liste des restaurants, menu, panier, commande, suivi
    /resto/vendeur/    vendeur  : ses restaurants, son menu (plats + options), ses commandes, ses livreurs
    /resto/livreur/    livreur  : commandes à prendre, position GPS, livraison en cours

Conventions (mêmes que le Bazar) : vues fonctionnelles, @login_required,
JsonResponse pour l'AJAX, messages + redirect pour le HTML.
"""
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .forms import CheckoutForm, CourierForm, MenuCategoryForm, MenuItemForm, RestaurantForm
from .models import (
    Cart, CartItem, Courier, MenuCategory, MenuItem, Option, OptionGroup,
    Order, OrderEvent, OrderItem, OrderItemOption, Restaurant,
)

PAGE_SIZE = 12


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _heic(upload):
    """Réutilise la conversion HEIC → JPEG du Bazar (photos iPhone)."""
    try:
        from bazar.views import _heic_to_jpeg
        return _heic_to_jpeg(upload)
    except Exception:
        return upload


def _json_body(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        return {}


def _user_cart(user):
    try:
        return user.resto_cart
    except Cart.DoesNotExist:
        return None


def _cart_summary(cart):
    if cart is None:
        return {'restaurant': None, 'count': 0, 'subtotal': 0, 'total': 0, 'lines': []}
    lines = list(cart.lines.select_related('item').prefetch_related('options'))
    return {
        'restaurant': {'name': cart.restaurant.name, 'slug': cart.restaurant.slug},
        'count': sum(l.quantity for l in lines),
        'subtotal': int(sum(l.line_total for l in lines)),
        'delivery_fee': int(cart.delivery_fee),
        'total': int(sum(l.line_total for l in lines) + cart.delivery_fee),
        'lines': [{
            'id': l.pk, 'name': l.item.name, 'quantity': l.quantity,
            'options': l.options_label, 'note': l.note,
            'unit_price': int(l.unit_price), 'line_total': int(l.line_total),
        } for l in lines],
    }


def _notify(target, from_user, verb, url, obj, push_title=None):
    """Notification in-app (+ push si configuré). Ne casse jamais la vue en cas d'erreur."""
    try:
        from notification.models import Notification, PushSubscription
        Notification.objects.create(
            target=target, from_user=from_user, verb=verb, redirect_url=url,
            content_type=ContentType.objects.get_for_model(obj), object_id=str(obj.pk),
        )
        PushSubscription.send_notification(target, push_title or 'Vazimba Resto', verb, url)
    except Exception:
        pass


def _owner_restaurant(request, slug):
    """Restaurant dont l'utilisateur courant est propriétaire, sinon 404."""
    return get_object_or_404(Restaurant, slug=slug, owner=request.user)


def _order_actor(order, user):
    """Rôle de `user` vis-à-vis de la commande : customer / restaurant / courier / None."""
    if order.customer_id == user.pk:
        return 'customer'
    if order.restaurant.owner_id == user.pk:
        return 'restaurant'
    if order.courier_id and order.courier.user_id == user.pk:
        return 'courier'
    return None


def _order_payload(order):
    """État complet d'une commande pour le suivi (JSON)."""
    courier = None
    if order.courier:
        c = order.courier
        courier = {
            'name': c.display_name, 'phone': c.phone, 'vehicle': c.get_vehicle_display(),
            'lat': c.latitude, 'lng': c.longitude,
            'updated_at': c.position_updated_at.isoformat() if c.position_updated_at else None,
        }
    return {
        'number': order.number,
        'status': order.status,
        'status_label': order.get_status_display(),
        'is_final': order.is_final,
        'is_cancelled': order.is_cancelled,
        'mode': order.mode,
        'estimated_minutes': order.estimated_minutes,
        'steps': order.progress_steps,
        'pickup': {'address': order.pickup_address, 'lat': order.pickup_latitude, 'lng': order.pickup_longitude,
                   'name': order.restaurant.name},
        'delivery': {'address': order.delivery_address, 'lat': order.delivery_latitude, 'lng': order.delivery_longitude},
        'courier': courier,
        'events': [{'status': e.status, 'label': e.get_status_display(), 'at': e.at.isoformat(),
                    'note': e.note} for e in order.events.all()],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CLIENT — liste des restaurants
# ═══════════════════════════════════════════════════════════════════════════════

def resto_index(request):
    """Page principale : restaurants approuvés, filtres catégorie / région / recherche."""
    from regions import REGION_CHOICES, REGION_LABELS

    qs = Restaurant.objects.filter(is_approved=True, is_active=True).select_related('owner')

    q      = (request.GET.get('q') or '').strip()
    cat    = request.GET.get('cat') or ''
    region = request.GET.get('region') or ''
    sort   = request.GET.get('sort') or 'open'

    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q) |
                       Q(address__icontains=q) | Q(items__name__icontains=q)).distinct()
    if cat:
        qs = qs.filter(category=cat)
    if region:
        qs = qs.filter(region=region)

    if sort == 'popular':
        qs = qs.order_by('-views_count', '-created_at')
    elif sort == 'recent':
        qs = qs.order_by('-created_at')
    elif sort == 'fee':
        qs = qs.order_by('delivery_fee', '-created_at')
    else:  # 'open' : ouverts d'abord
        qs = qs.order_by('-is_open', '-views_count', '-created_at')

    paginator = Paginator(qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))

    user_region = ''
    if request.user.is_authenticated:
        user_region = getattr(request.user, 'region', '') or ''

    cart = _user_cart(request.user) if request.user.is_authenticated else None

    return render(request, 'resto/index.html', {
        'page_obj': page_obj, 'total': paginator.count,
        'q': q, 'sel_cat': cat, 'sel_region': region, 'sort': sort,
        'categories': Restaurant.CATEGORY_CHOICES,
        'regions': [r for r in REGION_CHOICES if r[0]], 'region_labels': REGION_LABELS,
        'user_region': user_region,
        'cart_summary': _cart_summary(cart),
        'my_restaurants': request.user.restaurants.exists() if request.user.is_authenticated else False,
    })


def restaurant_detail(request, slug):
    """Menu d'un restaurant, groupé par rubrique, avec le panier en cours."""
    restaurant = get_object_or_404(Restaurant, slug=slug)
    is_owner = request.user.is_authenticated and restaurant.owner_id == request.user.pk
    if not restaurant.is_visible and not is_owner and not request.user.is_staff:
        raise Http404
    if not is_owner:
        restaurant.increment_views()

    items = (restaurant.items.filter(is_available=True)
             .select_related('category')
             .prefetch_related(Prefetch('option_groups', queryset=OptionGroup.objects.prefetch_related('options'))))
    # Regroupement par rubrique (les plats sans rubrique vont dans « Autres »)
    sections, by_cat = [], {}
    for cat in restaurant.menu_categories.all():
        by_cat[cat.pk] = {'name': cat.name, 'items': []}
        sections.append(by_cat[cat.pk])
    others = {'name': _('Autres'), 'items': []}
    for it in items:
        (by_cat.get(it.category_id) or others)['items'].append(it)
    if others['items']:
        sections.append(others)
    sections = [s for s in sections if s['items']]

    cart = _user_cart(request.user) if request.user.is_authenticated else None
    cart_same = cart if (cart and cart.restaurant_id == restaurant.pk) else None

    return render(request, 'resto/restaurant.html', {
        'restaurant': restaurant, 'sections': sections, 'is_owner': is_owner,
        'cart_summary': _cart_summary(cart_same),
        'other_cart': _cart_summary(cart) if (cart and not cart_same) else None,
    })


def item_options(request, slug, item_pk):
    """JSON : fiche d'un plat et ses groupes d'options (pour la fenêtre d'ajout au panier)."""
    item = get_object_or_404(MenuItem.objects.select_related('restaurant'), pk=item_pk, restaurant__slug=slug)
    groups = []
    for g in item.option_groups.prefetch_related('options'):
        groups.append({
            'id': g.pk, 'name': g.name, 'min': g.min_select, 'max': g.max_select,
            'required': g.is_required, 'single': g.is_single,
            'options': [{'id': o.pk, 'name': o.name, 'extra_price': int(o.extra_price)}
                        for o in g.options.all() if o.is_available],
        })
    return JsonResponse({
        'id': item.pk, 'name': item.name, 'description': item.description,
        'price': int(item.price), 'image': item.image.url if item.image else '',
        'available': item.is_available and item.restaurant.can_order,
        'groups': groups,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# CLIENT — panier
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def cart_view(request):
    cart = _user_cart(request.user)
    return render(request, 'resto/cart.html', {
        'cart': cart, 'cart_summary': _cart_summary(cart),
    })


@login_required
@require_POST
def cart_add(request, item_pk):
    """
    AJAX : ajoute un plat au panier avec ses options.
    Corps JSON : {quantity, note, options: [option_id…], replace: bool}
    Si le panier contient un autre restaurant, renvoie 409 sauf si replace=true.
    """
    item = get_object_or_404(MenuItem.objects.select_related('restaurant'), pk=item_pk, is_available=True)
    restaurant = item.restaurant
    if not restaurant.can_order:
        return JsonResponse({'error': _('Ce restaurant n\'accepte pas de commande pour le moment.')}, status=400)

    body = _json_body(request)
    try:
        quantity = max(1, min(20, int(body.get('quantity', 1))))
    except (TypeError, ValueError):
        quantity = 1
    note = (body.get('note') or '')[:200]
    option_ids = {int(x) for x in body.get('options', []) if str(x).isdigit()}

    # ── Validation des options contre les groupes du plat ─────────────────────
    chosen = []
    for g in item.option_groups.prefetch_related('options'):
        picked = [o for o in g.options.all() if o.pk in option_ids and o.is_available]
        if len(picked) < g.min_select:
            return JsonResponse({'error': _('« %(g)s » : choisissez au moins %(n)d option(s).') % {'g': g.name, 'n': g.min_select}}, status=400)
        if g.max_select and len(picked) > g.max_select:
            return JsonResponse({'error': _('« %(g)s » : %(n)d choix maximum.') % {'g': g.name, 'n': g.max_select}}, status=400)
        chosen.extend(picked)

    # ── Un seul restaurant à la fois ──────────────────────────────────────────
    cart = _user_cart(request.user)
    if cart and cart.restaurant_id != restaurant.pk:
        if not body.get('replace'):
            return JsonResponse({'conflict': True, 'current_restaurant': cart.restaurant.name}, status=409)
        cart.delete()
        cart = None
    if cart is None:
        cart = Cart.objects.create(user=request.user, restaurant=restaurant)

    # Même plat + mêmes options + même note → on incrémente la quantité
    chosen_ids = {o.pk for o in chosen}
    for line in cart.lines.filter(item=item, note=note).prefetch_related('options'):
        if {o.pk for o in line.options.all()} == chosen_ids:
            line.quantity = min(20, line.quantity + quantity)
            line.save(update_fields=['quantity'])
            break
    else:
        line = CartItem.objects.create(cart=cart, item=item, quantity=quantity, note=note)
        if chosen:
            line.options.set(chosen)

    return JsonResponse({'success': True, 'cart': _cart_summary(cart)})


@login_required
@require_POST
def cart_update_line(request, line_pk):
    """AJAX : {quantity} — 0 supprime la ligne."""
    cart = _user_cart(request.user)
    if cart is None:
        return JsonResponse({'error': 'empty'}, status=404)
    line = get_object_or_404(CartItem, pk=line_pk, cart=cart)
    try:
        qty = int(_json_body(request).get('quantity', 0))
    except (TypeError, ValueError):
        qty = 0
    if qty <= 0:
        line.delete()
    else:
        line.quantity = min(20, qty)
        line.save(update_fields=['quantity'])
    if not cart.lines.exists():
        cart.delete()
        cart = None
    return JsonResponse({'success': True, 'cart': _cart_summary(cart)})


@login_required
@require_POST
def cart_clear(request):
    cart = _user_cart(request.user)
    if cart:
        cart.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
        return JsonResponse({'success': True, 'cart': _cart_summary(None)})
    return redirect('resto:index')


# ═══════════════════════════════════════════════════════════════════════════════
# CLIENT — commander & suivre
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def checkout(request):
    cart = _user_cart(request.user)
    if cart is None or not cart.lines.exists():
        messages.info(request, _('Votre panier est vide.'))
        return redirect('resto:index')
    restaurant = cart.restaurant
    if not restaurant.can_order:
        messages.error(request, _('%(r)s n\'accepte pas de commande pour le moment.') % {'r': restaurant.name})
        return redirect('resto:restaurant', slug=restaurant.slug)

    summary = _cart_summary(cart)
    if restaurant.min_order and summary['subtotal'] < restaurant.min_order:
        messages.error(request, _('Commande minimum : %(m)s Ar.') % {'m': int(restaurant.min_order)})
        return redirect('resto:cart')

    initial = {
        'customer_name': request.user.username,
        'customer_phone': getattr(request.user, 'phone_number', '') or '',
    }
    last = Order.objects.filter(customer=request.user).exclude(delivery_address='').first()
    if last:
        initial.update({'delivery_address': last.delivery_address,
                        'delivery_latitude': last.delivery_latitude, 'delivery_longitude': last.delivery_longitude})

    if request.method == 'POST':
        form = CheckoutForm(request.POST, restaurant=restaurant)
        if form.is_valid():
            with transaction.atomic():
                order = form.save(commit=False)
                order.customer = request.user
                order.restaurant = restaurant
                order.pickup_address = restaurant.address
                order.pickup_latitude, order.pickup_longitude = restaurant.latitude, restaurant.longitude
                order.subtotal = summary['subtotal']
                order.delivery_fee = restaurant.delivery_fee if order.is_delivery else 0
                order.total = order.subtotal + order.delivery_fee
                order.estimated_minutes = restaurant.avg_prep_minutes + (20 if order.is_delivery else 0)
                if not order.is_delivery:
                    order.delivery_address, order.delivery_latitude, order.delivery_longitude = '', None, None
                order.save()
                for line in cart.lines.select_related('item').prefetch_related('options__group'):
                    oi = OrderItem.objects.create(
                        order=order, item=line.item, name=line.item.name,
                        unit_price=line.unit_price, quantity=line.quantity,
                        line_total=line.line_total, note=line.note,
                    )
                    OrderItemOption.objects.bulk_create([
                        OrderItemOption(line=oi, group_name=o.group.name, name=o.name, extra_price=o.extra_price)
                        for o in line.options.all()
                    ])
                OrderEvent.objects.create(order=order, status=Order.STATUS_PENDING, by=request.user)
                cart.delete()

            url = reverse('resto:vendor_orders', kwargs={'slug': restaurant.slug})
            _notify(restaurant.owner, request.user,
                    _('Nouvelle commande %(n)s chez %(r)s (%(t)s)') % {'n': order.number, 'r': restaurant.name, 't': order.formatted_total},
                    url, order, push_title=_('🍽️ Nouvelle commande'))
            messages.success(request, _('Commande %(n)s envoyée ! Le restaurant va la confirmer.') % {'n': order.number})
            return redirect('resto:order', number=order.number)
    else:
        form = CheckoutForm(initial=initial, restaurant=restaurant)

    return render(request, 'resto/checkout.html', {
        'form': form, 'cart': cart, 'cart_summary': summary, 'restaurant': restaurant,
    })


@login_required
def my_orders(request):
    qs = (Order.objects.filter(customer=request.user)
          .select_related('restaurant').prefetch_related('items'))
    active = [o for o in qs if not o.is_final]
    past = [o for o in qs if o.is_final][:30]
    return render(request, 'resto/my_orders.html', {'active': active, 'past': past})


@login_required
def order_detail(request, number):
    order = get_object_or_404(
        Order.objects.select_related('restaurant', 'restaurant__owner', 'courier', 'courier__user', 'customer'),
        number=number,
    )
    actor = _order_actor(order, request.user)
    if actor is None and not request.user.is_staff:
        raise Http404
    items = order.items.prefetch_related('options')
    return render(request, 'resto/order.html', {
        'order': order, 'items': items, 'actor': actor,
        'transitions': [(s, dict(Order.STATUS_CHOICES)[s]) for s in order.allowed_transitions(actor)] if actor else [],
        'state_json': json.dumps(_order_payload(order)),
    })


@login_required
def order_state(request, number):
    """JSON de suivi (interrogé toutes les quelques secondes par la page de commande)."""
    order = get_object_or_404(Order.objects.select_related('restaurant', 'courier', 'courier__user'), number=number)
    if _order_actor(order, request.user) is None and not request.user.is_staff:
        return JsonResponse({'error': 'forbidden'}, status=403)
    return JsonResponse(_order_payload(order))


@login_required
@require_POST
def order_cancel(request, number):
    order = get_object_or_404(Order, number=number, customer=request.user)
    if not order.can_customer_cancel:
        messages.error(request, _('Cette commande ne peut plus être annulée.'))
    else:
        order.set_status(Order.STATUS_CANCELLED, by=request.user, note=_('Annulée par le client'))
        _notify(order.restaurant.owner, request.user,
                _('Commande %(n)s annulée par le client') % {'n': order.number},
                reverse('resto:vendor_orders', kwargs={'slug': order.restaurant.slug}), order)
        messages.success(request, _('Commande annulée.'))
    return redirect('resto:order', number=order.number)


# ═══════════════════════════════════════════════════════════════════════════════
# STATUTS — restaurant & livreur
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@require_POST
def order_set_status(request, number):
    """POST {status, note?} — restaurant ou livreur fait avancer la commande."""
    order = get_object_or_404(Order.objects.select_related('restaurant', 'courier', 'customer'), number=number)
    actor = _order_actor(order, request.user)
    body = _json_body(request) if request.content_type == 'application/json' else request.POST
    new_status = body.get('status', '')
    note = (body.get('note') or '')[:200]

    if actor not in ('restaurant', 'courier') or new_status not in order.allowed_transitions(actor):
        msg = _('Transition non autorisée.')
        if request.content_type == 'application/json':
            return JsonResponse({'error': msg}, status=403)
        messages.error(request, msg)
        return redirect('resto:order', number=order.number)

    if actor == 'restaurant' and new_status == Order.STATUS_ACCEPTED:
        try:
            est = int(body.get('estimated_minutes') or 0)
            if est > 0:
                order.estimated_minutes = min(est, 240)
        except (TypeError, ValueError):
            pass
    order.set_status(new_status, by=request.user, note=note)

    # ── Notifier le client (et les livreurs quand c'est prêt) ─────────────────
    url = reverse('resto:order', kwargs={'number': order.number})
    _notify(order.customer, request.user,
            _('Commande %(n)s : %(s)s') % {'n': order.number, 's': order.get_status_display()},
            url, order, push_title=_('🍽️ %(r)s') % {'r': order.restaurant.name})
    if new_status == Order.STATUS_READY and order.is_delivery and order.courier is None:
        for c in Courier.objects.filter(restaurant=order.restaurant, is_approved=True, is_available=True).select_related('user'):
            _notify(c.user, request.user,
                    _('Commande %(n)s prête à récupérer chez %(r)s') % {'n': order.number, 'r': order.restaurant.name},
                    reverse('resto:courier_dashboard'), order, push_title=_('🛵 Livraison disponible'))

    if request.content_type == 'application/json':
        return JsonResponse({'success': True, 'state': _order_payload(order)})
    messages.success(request, _('Commande %(n)s → %(s)s') % {'n': order.number, 's': order.get_status_display()})
    return redirect(request.POST.get('next') or url)


# ═══════════════════════════════════════════════════════════════════════════════
# VENDEUR
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def vendor_dashboard(request):
    restaurants = (request.user.restaurants
                   .annotate(pending=Count('orders', filter=Q(orders__status=Order.STATUS_PENDING)),
                             active=Count('orders', filter=Q(orders__status__in=[
                                 Order.STATUS_ACCEPTED, Order.STATUS_PREPARING, Order.STATUS_READY,
                                 Order.STATUS_PICKED_UP, Order.STATUS_DELIVERING])),
                             items_count=Count('items', distinct=True)))
    return render(request, 'resto/vendor/dashboard.html', {'restaurants': restaurants})


@login_required
def restaurant_create(request):
    if request.method == 'POST':
        form = RestaurantForm(request.POST, request.FILES)
        if form.is_valid():
            r = form.save(commit=False)
            r.owner = request.user
            if not r.region:
                r.region = getattr(request.user, 'region', '') or ''
            for f in ('logo', 'banner'):
                if request.FILES.get(f):
                    setattr(r, f, _heic(request.FILES[f]))
            r.save()
            messages.success(request, _('Restaurant créé. Ajoutez votre menu, puis Vazimba validera votre page.'))
            return redirect('resto:menu_manage', slug=r.slug)
    else:
        form = RestaurantForm(initial={'region': getattr(request.user, 'region', '') or '',
                                       'phone': getattr(request.user, 'phone_number', '') or ''})
    return render(request, 'resto/vendor/restaurant_form.html', {'form': form, 'restaurant': None})


@login_required
def restaurant_edit(request, slug):
    restaurant = _owner_restaurant(request, slug)
    if request.method == 'POST':
        form = RestaurantForm(request.POST, request.FILES, instance=restaurant)
        if form.is_valid():
            r = form.save(commit=False)
            for f in ('logo', 'banner'):
                if request.FILES.get(f):
                    setattr(r, f, _heic(request.FILES[f]))
            r.save()
            messages.success(request, _('Restaurant mis à jour.'))
            return redirect('resto:vendor_dashboard')
    else:
        form = RestaurantForm(instance=restaurant)
    return render(request, 'resto/vendor/restaurant_form.html', {'form': form, 'restaurant': restaurant})


@login_required
@require_POST
def toggle_open(request, slug):
    restaurant = _owner_restaurant(request, slug)
    restaurant.is_open = not restaurant.is_open
    restaurant.save(update_fields=['is_open'])
    if request.content_type == 'application/json':
        return JsonResponse({'success': True, 'is_open': restaurant.is_open})
    messages.success(request, _('Restaurant ouvert aux commandes.') if restaurant.is_open else _('Commandes suspendues.'))
    return redirect(request.POST.get('next') or 'resto:vendor_dashboard')


@login_required
def menu_manage(request, slug):
    restaurant = _owner_restaurant(request, slug)
    categories = restaurant.menu_categories.all()
    items = (restaurant.items.select_related('category')
             .prefetch_related(Prefetch('option_groups', queryset=OptionGroup.objects.prefetch_related('options'))))
    # Données pour l'éditeur d'options (JS)
    options_json = {
        it.pk: [{'name': g.name, 'min': g.min_select, 'max': g.max_select,
                 'options': [{'name': o.name, 'extra_price': int(o.extra_price)} for o in g.options.all()]}
                for g in it.option_groups.all()]
        for it in items
    }
    return render(request, 'resto/vendor/menu.html', {
        'restaurant': restaurant, 'categories': categories, 'items': items,
        'item_form': MenuItemForm(restaurant=restaurant), 'cat_form': MenuCategoryForm(),
        'options_json': json.dumps(options_json),
    })


@login_required
@require_POST
def category_save(request, slug):
    """POST name, order, [pk], [delete=1]"""
    restaurant = _owner_restaurant(request, slug)
    pk = request.POST.get('pk')
    cat = get_object_or_404(MenuCategory, pk=pk, restaurant=restaurant) if pk else None
    if cat and request.POST.get('delete'):
        cat.delete()
        messages.success(request, _('Rubrique supprimée (les plats sont conservés).'))
        return redirect('resto:menu_manage', slug=slug)
    form = MenuCategoryForm(request.POST, instance=cat)
    if form.is_valid():
        c = form.save(commit=False)
        c.restaurant = restaurant
        c.save()
        messages.success(request, _('Rubrique enregistrée.'))
    else:
        messages.error(request, _('Nom de rubrique invalide.'))
    return redirect('resto:menu_manage', slug=slug)


@login_required
@require_POST
def item_save(request, slug, item_pk=None):
    restaurant = _owner_restaurant(request, slug)
    item = get_object_or_404(MenuItem, pk=item_pk, restaurant=restaurant) if item_pk else None
    form = MenuItemForm(request.POST, request.FILES, instance=item, restaurant=restaurant)
    if form.is_valid():
        it = form.save(commit=False)
        it.restaurant = restaurant
        if request.FILES.get('image'):
            it.image = _heic(request.FILES['image'])
        it.save()
        messages.success(request, _('Plat enregistré : %(n)s') % {'n': it.name})
    else:
        messages.error(request, _('Formulaire invalide : ') + '; '.join(f'{k}: {v[0]}' for k, v in form.errors.items()))
    return redirect('resto:menu_manage', slug=slug)


@login_required
@require_POST
def item_delete(request, slug, item_pk):
    restaurant = _owner_restaurant(request, slug)
    item = get_object_or_404(MenuItem, pk=item_pk, restaurant=restaurant)
    item.delete()
    messages.success(request, _('Plat supprimé.'))
    return redirect('resto:menu_manage', slug=slug)


@login_required
@require_POST
def item_options_save(request, slug, item_pk):
    """
    AJAX JSON : remplace intégralement les groupes d'options d'un plat.
    Corps : {groups: [{name, min, max, options: [{name, extra_price}]}]}
    """
    restaurant = _owner_restaurant(request, slug)
    item = get_object_or_404(MenuItem, pk=item_pk, restaurant=restaurant)
    groups = _json_body(request).get('groups') or []
    if not isinstance(groups, list) or len(groups) > 10:
        return JsonResponse({'error': _('Données invalides.')}, status=400)

    with transaction.atomic():
        item.option_groups.all().delete()
        for gi, g in enumerate(groups):
            name = (g.get('name') or '').strip()[:100]
            opts = [o for o in (g.get('options') or []) if (o.get('name') or '').strip()][:30]
            if not name or not opts:
                continue
            try:
                mn = max(0, int(g.get('min', 0))); mx = max(0, int(g.get('max', 1)))
            except (TypeError, ValueError):
                mn, mx = 0, 1
            if mx and mn > mx:
                mn = mx
            og = OptionGroup.objects.create(item=item, name=name, min_select=mn, max_select=mx, order=gi)
            Option.objects.bulk_create([
                Option(group=og, name=(o.get('name') or '').strip()[:100],
                       extra_price=max(0, int(o.get('extra_price') or 0)), order=oi)
                for oi, o in enumerate(opts)
            ])
    return JsonResponse({'success': True, 'groups': item.option_groups.count()})


@login_required
def vendor_orders(request, slug):
    restaurant = _owner_restaurant(request, slug)
    tab = request.GET.get('tab') or 'active'
    qs = restaurant.orders.select_related('customer', 'courier', 'courier__user').prefetch_related('items__options')
    if tab == 'pending':
        qs = qs.filter(status=Order.STATUS_PENDING)
    elif tab == 'active':
        qs = qs.exclude(status__in=Order.FINAL_STATUSES)
    elif tab == 'done':
        qs = qs.filter(status__in=Order.FINAL_STATUSES)[:50]

    if request.GET.get('json'):
        # Pour le rafraîchissement automatique de la page vendeur
        return JsonResponse({
            'pending': restaurant.orders.filter(status=Order.STATUS_PENDING).count(),
            'active': restaurant.orders.exclude(status__in=Order.FINAL_STATUSES).count(),
            'latest': [{'number': o.number, 'status': o.status} for o in restaurant.orders.all()[:20]],
        })

    orders = list(qs)
    for o in orders:
        o.next_steps = [(s, dict(Order.STATUS_CHOICES)[s]) for s in o.allowed_transitions('restaurant')]
    return render(request, 'resto/vendor/orders.html', {
        'restaurant': restaurant, 'orders': orders, 'tab': tab,
        'pending_count': restaurant.orders.filter(status=Order.STATUS_PENDING).count(),
    })


@login_required
def vendor_couriers(request, slug):
    """Livreurs rattachés au restaurant : ajout par nom d'utilisateur, retrait."""
    restaurant = _owner_restaurant(request, slug)
    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        remove_pk = request.POST.get('remove')
        if remove_pk:
            Courier.objects.filter(pk=remove_pk, restaurant=restaurant).update(restaurant=None)
            messages.success(request, _('Livreur retiré.'))
        elif username:
            from django.contrib.auth import get_user_model
            user = get_user_model().objects.filter(username__iexact=username).first()
            if not user:
                messages.error(request, _('Utilisateur introuvable : %(u)s') % {'u': username})
            else:
                courier, _created = Courier.objects.get_or_create(
                    user=user, defaults={'phone': getattr(user, 'phone_number', '') or '', 'region': restaurant.region})
                courier.restaurant = restaurant
                courier.is_approved = True   # le restaurant se porte garant de ses livreurs
                courier.save(update_fields=['restaurant', 'is_approved'])
                _notify(user, request.user,
                        _('%(r)s vous a ajouté comme livreur') % {'r': restaurant.name},
                        reverse('resto:courier_dashboard'), restaurant, push_title=_('🛵 Vazimba Resto'))
                messages.success(request, _('%(u)s est maintenant livreur de %(r)s.') % {'u': user.username, 'r': restaurant.name})
        return redirect('resto:vendor_couriers', slug=slug)
    return render(request, 'resto/vendor/couriers.html', {
        'restaurant': restaurant, 'couriers': restaurant.couriers.select_related('user'),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# LIVREUR
# ═══════════════════════════════════════════════════════════════════════════════

def _courier(user):
    try:
        return user.courier_profile
    except Courier.DoesNotExist:
        return None


@login_required
def courier_signup(request):
    courier = _courier(request.user)
    if request.method == 'POST':
        form = CourierForm(request.POST, instance=courier)
        if form.is_valid():
            c = form.save(commit=False)
            c.user = request.user
            c.save()
            messages.success(request, _('Profil livreur enregistré.') if courier else
                             _('Demande envoyée. Un restaurant peut vous rattacher, ou Vazimba validera votre profil.'))
            return redirect('resto:courier_dashboard')
    else:
        form = CourierForm(instance=courier, initial=None if courier else {
            'phone': getattr(request.user, 'phone_number', '') or '',
            'region': getattr(request.user, 'region', '') or '',
        })
    return render(request, 'resto/courier/signup.html', {'form': form, 'courier': courier})


@login_required
def courier_dashboard(request):
    courier = _courier(request.user)
    if courier is None:
        return redirect('resto:courier_signup')

    mine = (Order.objects.filter(courier=courier)
            .exclude(status__in=Order.FINAL_STATUSES)
            .select_related('restaurant', 'customer').prefetch_related('items'))
    available = Order.objects.none()
    if courier.is_approved:
        available = (Order.objects.filter(status=Order.STATUS_READY, mode=Order.MODE_DELIVERY, courier__isnull=True)
                     .select_related('restaurant').prefetch_related('items'))
        if courier.restaurant_id:
            available = available.filter(restaurant=courier.restaurant)
        elif courier.region:
            # Indépendant : commandes de sa région dont le restaurant n'a pas de livreur attitré disponible
            available = available.filter(restaurant__region=courier.region)
    history = Order.objects.filter(courier=courier, status=Order.STATUS_DELIVERED).select_related('restaurant')[:20]

    orders = list(mine)
    for o in orders:
        o.next_steps = [(s, dict(Order.STATUS_CHOICES)[s]) for s in o.allowed_transitions('courier')]
    return render(request, 'resto/courier/dashboard.html', {
        'courier': courier, 'orders': orders, 'available': available, 'history': history,
    })


@login_required
@require_POST
def courier_toggle(request):
    courier = _courier(request.user)
    if courier is None:
        return JsonResponse({'error': 'no_profile'}, status=404)
    courier.is_available = not courier.is_available
    courier.save(update_fields=['is_available'])
    if request.content_type == 'application/json':
        return JsonResponse({'success': True, 'is_available': courier.is_available})
    return redirect('resto:courier_dashboard')


@login_required
@require_POST
def courier_position(request):
    """AJAX : {lat, lng} envoyé périodiquement par le téléphone du livreur."""
    courier = _courier(request.user)
    if courier is None:
        return JsonResponse({'error': 'no_profile'}, status=404)
    body = _json_body(request)
    try:
        lat, lng = float(body['lat']), float(body['lng'])
    except (KeyError, TypeError, ValueError):
        return JsonResponse({'error': 'bad_coords'}, status=400)
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return JsonResponse({'error': 'bad_coords'}, status=400)
    courier.update_position(lat, lng)
    return JsonResponse({'success': True, 'at': courier.position_updated_at.isoformat()})


@login_required
@require_POST
def courier_take(request, number):
    courier = _courier(request.user)
    if courier is None or not courier.is_approved:
        messages.error(request, _('Profil livreur non validé.'))
        return redirect('resto:courier_dashboard')
    with transaction.atomic():
        order = (Order.objects.select_for_update().select_related('restaurant')
                 .filter(number=number, status=Order.STATUS_READY, mode=Order.MODE_DELIVERY, courier__isnull=True).first())
        if order is None:
            messages.error(request, _('Cette commande n\'est plus disponible.'))
            return redirect('resto:courier_dashboard')
        if courier.restaurant_id and courier.restaurant_id != order.restaurant_id:
            messages.error(request, _('Cette commande appartient à un autre restaurant.'))
            return redirect('resto:courier_dashboard')
        order.courier = courier
        order.save(update_fields=['courier'])
        order.set_status(Order.STATUS_PICKED_UP, by=request.user, note=_('Prise en charge par %(c)s') % {'c': courier.display_name})

    url = reverse('resto:order', kwargs={'number': order.number})
    _notify(order.customer, request.user,
            _('%(c)s a récupéré votre commande %(n)s') % {'c': courier.display_name, 'n': order.number},
            url, order, push_title=_('🛵 En route !'))
    _notify(order.restaurant.owner, request.user,
            _('Commande %(n)s prise par %(c)s') % {'n': order.number, 'c': courier.display_name},
            reverse('resto:vendor_orders', kwargs={'slug': order.restaurant.slug}), order)
    messages.success(request, _('Commande %(n)s prise en charge. Bonne route !') % {'n': order.number})
    return redirect('resto:order', number=order.number)
