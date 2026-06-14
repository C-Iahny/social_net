from django.urls import path
from . import views

app_name = 'legal'

urlpatterns = [
    path('cgu/', views.cgu_view, name='cgu'),
    path('confidentialite/', views.confidentialite_view, name='confidentialite'),
]
