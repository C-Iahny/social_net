from django.shortcuts import render
from django.conf import settings
from django.utils import timezone
from django.db import models

from .models import Announcement

DEBUG = False


def home_screen_view(request):
	context = {}
	context['debug_mode'] = settings.DEBUG
	context['debug'] = DEBUG
	context['room_id'] = "1"
	return render(request, "personal/home.html", context)


def landing_view(request):
	"""
	Vue de la landing page publique.
	Affiche les annonces actives selon la date/heure courante.
	"""
	now = timezone.now()

	announcements = Announcement.objects.filter(
		is_active=True,
		start_date__lte=now,
	).filter(
		models.Q(end_date__isnull=True) | models.Q(end_date__gte=now)
	).order_by('-start_date')

	context = {
		'announcements': announcements,
		'page_title': 'Bienvenue sur ZOOT',
	}
	return render(request, "personal/landing.html", context)
