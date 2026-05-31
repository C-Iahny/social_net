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
]
