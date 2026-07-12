from django.urls import path
from . import views

app_name = 'tourisme'

urlpatterns = [
    path('',                     views.tourisme_home,   name='home'),
    path('lieux/',               views.lieux_list,      name='lieux_list'),
    path('lieux/<slug:slug>/',   views.lieu_detail,     name='lieu_detail'),
    path('guides/',              views.guides_list,     name='guides_list'),
    path('guides/<int:pk>/',     views.guide_profile,   name='guide_profile'),
    path('guides/inscription/',  views.guide_register,  name='guide_register'),
]
