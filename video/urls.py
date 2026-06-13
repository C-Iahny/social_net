from django.urls import path
from . import views

app_name = 'video'

urlpatterns = [
    path('',                   views.live_list,       name='live-list'),
    path('create/',            views.live_create,     name='live-create'),
    path('<int:room_id>/',     views.live_room,       name='live-room'),
    path('<int:room_id>/end/', views.live_end,        name='live-end'),
    path('api/active/',        views.live_api_active, name='live-api-active'),
]
