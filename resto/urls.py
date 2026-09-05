from django.urls import path
from . import views

app_name = 'resto'

urlpatterns = [
    # ── Client ─────────────────────────────────────────────────────────────────
    path('',                                  views.resto_index,      name='index'),
    path('r/<slug:slug>/',                    views.restaurant_detail, name='restaurant'),
    path('r/<slug:slug>/plat/<int:item_pk>/', views.item_options,     name='item_options'),   # AJAX (JSON)
    path('panier/',                           views.cart_view,        name='cart'),
    path('panier/ajouter/<int:item_pk>/',     views.cart_add,         name='cart_add'),       # AJAX POST
    path('panier/ligne/<int:line_pk>/',       views.cart_update_line, name='cart_update'),    # AJAX POST
    path('panier/vider/',                     views.cart_clear,       name='cart_clear'),     # POST
    path('commander/',                        views.checkout,         name='checkout'),
    path('mes-commandes/',                    views.my_orders,        name='my_orders'),
    path('commande/<str:number>/',            views.order_detail,     name='order'),
    path('commande/<str:number>/etat/',       views.order_state,      name='order_state'),    # AJAX (JSON) polling
    path('commande/<str:number>/annuler/',    views.order_cancel,     name='order_cancel'),   # POST
    path('commande/<str:number>/avis/',       views.order_review,     name='order_review'),   # POST

    # ── Vendeur ────────────────────────────────────────────────────────────────
    path('vendeur/',                                     views.vendor_dashboard,  name='vendor_dashboard'),
    path('vendeur/nouveau/',                             views.restaurant_create, name='restaurant_create'),
    path('vendeur/<slug:slug>/modifier/',                views.restaurant_edit,   name='restaurant_edit'),
    path('vendeur/<slug:slug>/menu/',                    views.menu_manage,       name='menu_manage'),
    path('vendeur/<slug:slug>/menu/rubrique/',           views.category_save,     name='category_save'),   # POST
    path('vendeur/<slug:slug>/menu/plat/',               views.item_save,         name='item_save'),       # POST (créer)
    path('vendeur/<slug:slug>/menu/plat/<int:item_pk>/', views.item_save,         name='item_edit'),       # POST (modifier)
    path('vendeur/<slug:slug>/menu/plat/<int:item_pk>/supprimer/', views.item_delete, name='item_delete'),  # POST
    path('vendeur/<slug:slug>/menu/plat/<int:item_pk>/options/',   views.item_options_save, name='item_options_save'),  # POST (JSON)
    path('vendeur/<slug:slug>/commandes/',               views.vendor_orders,     name='vendor_orders'),
    path('vendeur/<slug:slug>/ouvert/',                  views.toggle_open,       name='toggle_open'),     # POST
    path('vendeur/<slug:slug>/livreurs/',                views.vendor_couriers,   name='vendor_couriers'),

    # ── Livreur ────────────────────────────────────────────────────────────────
    path('livreur/',                                     views.courier_dashboard, name='courier_dashboard'),
    path('livreur/inscription/',                         views.courier_signup,    name='courier_signup'),
    path('livreur/position/',                            views.courier_position,  name='courier_position'), # AJAX POST
    path('livreur/disponible/',                          views.courier_toggle,    name='courier_toggle'),   # POST
    path('livreur/commande/<str:number>/prendre/',       views.courier_take,      name='courier_take'),     # POST

    # ── Transitions de statut (restaurant / livreur) ───────────────────────────
    path('commande/<str:number>/statut/',                views.order_set_status,  name='order_set_status'), # POST
]
