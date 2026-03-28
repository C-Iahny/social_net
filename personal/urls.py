from django.urls import path
from .views import home_screen_view, landing_view

urlpatterns = [
	path('home/', home_screen_view, name='home'),
	path('landing/', landing_view, name='landing'),
]
