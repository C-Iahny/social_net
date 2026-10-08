"""
Achat depuis un post, une vidéo ou une story.

Un post peut pointer vers une annonce du Bazar ou un plat Resto appartenant
à son auteur. Ce module construit la « carte produit » affichée sous le post
et sur la vidéo, et liste les produits qu'un utilisateur peut lier.
"""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from django.utils.translation import gettext as _

from bazar.models import Annonce
from resto.models import MenuItem


def _image_url(field):
    try:
        return field.url if field else None
    except Exception:
        return None


def annonce_payload(annonce):
    available = annonce.status == 'active'
    price = annonce.formatted_prix_location if annonce.is_location else annonce.formatted_price
    return {
        'kind':      'bazar',
        'ref':       'bazar:%d' % annonce.pk,
        'id':        annonce.pk,
        'title':     annonce.title,
        'price':     price,
        'image':     _image_url(getattr(annonce.get_primary_image(), 'image', None)),
        'seller':    annonce.seller.username,
        'url':       reverse('bazar:detail', args=[annonce.pk]),
        'cta':       _('Louer') if annonce.is_location else _('Acheter'),
        'available': available,
        'badge':     _('Bazar'),
    }


def menu_item_payload(item):
    resto = item.restaurant
    available = item.is_available and resto.can_order
    return {
        'kind':      'resto',
        'ref':       'resto:%d' % item.pk,
        'id':        item.pk,
        'title':     item.name,
        'price':     item.formatted_price,
        'image':     _image_url(item.image),
        'seller':    resto.name,
        'url':       reverse('resto:restaurant', args=[resto.slug]) + '?plat=%d' % item.pk,
        'cta':       _('Commander'),
        'available': available,
        'badge':     _('Resto'),
    }


def product_for(post):
    """Carte produit d'un post, ou None. Utilise les FK déjà chargées."""
    if post.annonce_id:
        annonce = post.annonce
        if annonce is not None:
            return annonce_payload(annonce)
    if post.menu_item_id:
        item = post.menu_item
        if item is not None:
            return menu_item_payload(item)
    return None


def attach_products(posts):
    """Pose `post.product` sur chaque post en deux requêtes au plus."""
    posts = list(posts)
    annonce_ids = {p.annonce_id for p in posts if p.annonce_id}
    item_ids = {p.menu_item_id for p in posts if p.menu_item_id}
    annonces = {}
    if annonce_ids:
        annonces = {a.pk: a for a in Annonce.objects.filter(pk__in=annonce_ids)
                    .select_related('seller').prefetch_related('images')}
    items = {}
    if item_ids:
        items = {i.pk: i for i in MenuItem.objects.filter(pk__in=item_ids).select_related('restaurant')}
    for p in posts:
        product = None
        if p.annonce_id and p.annonce_id in annonces:
            product = annonce_payload(annonces[p.annonce_id])
        elif p.menu_item_id and p.menu_item_id in items:
            product = menu_item_payload(items[p.menu_item_id])
        p.product = product
    return posts


def user_products(user):
    """Produits que `user` peut lier : ses annonces actives, les plats de ses restos."""
    out = []
    for a in (Annonce.objects.filter(seller=user, status='active')
              .select_related('seller').prefetch_related('images').order_by('-created_at')[:60]):
        out.append(annonce_payload(a))
    for i in (MenuItem.objects.filter(restaurant__owner=user, is_available=True)
              .select_related('restaurant').order_by('restaurant__name', 'order', 'id')[:60]):
        out.append(menu_item_payload(i))
    return out


def resolve_product_ref(user, ref):
    """
    Transforme « bazar:12 » / « resto:34 » en (annonce, menu_item) en vérifiant
    que le produit appartient bien à `user`. Renvoie (None, None) sinon.
    """
    ref = (ref or '').strip()
    kind, _sep, pk = ref.partition(':')
    if not pk.isdigit():
        return None, None
    pk = int(pk)
    if kind == 'bazar':
        annonce = Annonce.objects.filter(pk=pk, seller=user).first()
        return annonce, None
    if kind == 'resto':
        item = MenuItem.objects.filter(pk=pk, restaurant__owner=user).first()
        return None, item
    return None, None


def apply_product_ref(post, user, ref, clear_if_empty=False):
    """Applique la référence produit du formulaire au post et sauvegarde si changé."""
    ref = (ref or '').strip()
    if not ref and not clear_if_empty:
        return
    annonce, item = resolve_product_ref(user, ref) if ref else (None, None)
    if post.annonce_id == getattr(annonce, 'pk', None) and post.menu_item_id == getattr(item, 'pk', None):
        return
    post.annonce = annonce
    post.menu_item = item
    post.save(update_fields=['annonce', 'menu_item'])


@login_required(login_url='login')
def my_products(request):
    """JSON : produits liables par l'utilisateur connecté (sélecteur du formulaire)."""
    return JsonResponse({'products': user_products(request.user)})
