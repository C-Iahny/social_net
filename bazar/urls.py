from django.urls import path
from . import views

app_name = 'bazar'

urlpatterns = [
    # ── Liste principale ───────────────────────────────────────────────────────
    path('',                    views.bazar_index,    name='index'),

    # ── Créer une annonce ──────────────────────────────────────────────────────
    path('vendre/',             views.annonce_create, name='create'),

    # ── Mes annonces ──────────────────────────────────────────────────────────
    path('mes-annonces/',       views.mes_annonces,   name='mes_annonces'),

    # ── Détail d'une annonce ───────────────────────────────────────────────────
    path('<int:pk>/',           views.annonce_detail, name='detail'),

    # ── Modifier ───────────────────────────────────────────────────────────────
    path('<int:pk>/modifier/',  views.annonce_edit,   name='edit'),

    # ── Supprimer annonce ──────────────────────────────────────────────────────
    path('<int:pk>/supprimer/', views.annonce_delete, name='delete'),

    # ── Marquer vendue ─────────────────────────────────────────────────────────
    path('<int:pk>/vendue/',    views.mark_sold,      name='mark_sold'),

    # ── Supprimer une image (AJAX) ─────────────────────────────────────────────
    path('image/<int:img_pk>/supprimer/', views.delete_image, name='delete_image'),

    # ── Bump (AJAX POST) ────────────────────────────────────────────────────────
    path('<int:pk>/bump/',          views.bump_annonce,   name='bump'),

    # ── Toggle statut active ↔ pause (AJAX POST) ────────────────────────────────
    path('<int:pk>/toggle-statut/', views.toggle_status,  name='toggle_status'),

    # ── Vérification vendeur ───────────────────────────────────────────────────
    path('verification/', views.request_verification, name='request_verification'),
]
