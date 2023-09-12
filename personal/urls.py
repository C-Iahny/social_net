from django.urls import path, include

from .views import home_screen_view



urlpatterns = [
	path('home/', home_screen_view, name='home'),
]









