from django.urls import path
from . import views

urlpatterns = [
    path('sw.js',         views.service_worker, name='service-worker'),
    path('manifest.json', views.manifest,        name='manifest'),
    path('offline/',      views.offline,         name='offline'),
]
