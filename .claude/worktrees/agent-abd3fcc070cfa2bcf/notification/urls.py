from django.urls import path
from . import views

app_name = 'notification'

urlpatterns = [
    path('push/key/',         views.vapid_public_key,      name='push-key'),
    path('push/subscribe/',   views.push_subscribe,        name='push-subscribe'),
    path('push/unsubscribe/', views.push_unsubscribe,      name='push-unsubscribe'),
    path('counts/',           views.unread_counts,         name='unread-counts'),
    path('journal/',          views.notification_journal,  name='journal'),
]
