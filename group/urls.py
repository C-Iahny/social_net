from django.urls import path

from . import views

app_name = 'group'

urlpatterns = [
    path('', views.group_list, name='list'),
    path('create/', views.group_create, name='create'),
    path('<slug:slug>/', views.group_detail, name='detail'),
    path('<slug:slug>/edit/', views.group_edit, name='edit'),
    path('<slug:slug>/delete/', views.group_delete, name='delete'),
    path('<slug:slug>/join/', views.group_join, name='join'),
    path('<slug:slug>/leave/', views.group_leave, name='leave'),
    path('<slug:slug>/post/', views.group_add_post, name='add-post'),
    # Gestion des posts
    path('<slug:slug>/pin/<int:post_id>/', views.group_pin_post, name='pin-post'),
    # Gestion des membres
    path('<slug:slug>/promote/<int:user_id>/', views.group_promote_member, name='promote-member'),
    path('<slug:slug>/demote/<int:user_id>/', views.group_demote_member, name='demote-member'),
    # Événements
    path('<slug:slug>/event/create/', views.group_event_create, name='event-create'),
    path('<slug:slug>/event/<int:event_id>/attend/', views.group_event_attend, name='event-attend'),
    # Invitations
    path('<slug:slug>/invite/search/', views.group_invite_search, name='invite-search'),
    path('<slug:slug>/invite/', views.group_invite_member, name='invite-member'),
    # Dina (charte communautaire)
    path('<slug:slug>/dina/save/', views.group_dina_save, name='dina-save'),
]
