from django.urls import path
from . import views

app_name = 'tourisme'

urlpatterns = [
    path('',                     views.tourisme_home,   name='home'),
    path('lieux/',               views.lieux_list,      name='lieux_list'),
    path('lieux/proposer/',               views.lieu_submit,  name='lieu_submit'),
    path('lieux/<slug:slug>/modifier/',   views.lieu_edit,    name='lieu_edit'),
    path('lieux/<slug:slug>/',            views.lieu_detail,  name='lieu_detail'),
    path('guides/',              views.guides_list,     name='guides_list'),
    path('guides/inscription/',  views.guide_register,  name='guide_register'),
    path('guides/<int:pk>/',     views.guide_profile,   name='guide_profile'),
]
