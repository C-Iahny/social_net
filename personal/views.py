from django.shortcuts import render
from django.conf import settings
from django.utils import timezone
from django.db import models

from .models import Announcement, HeroSettings

DEBUG = False


def home_screen_view(request):
	context = {}
	context['debug_mode'] = settings.DEBUG
	context['debug'] = DEBUG
	context['room_id'] = "1"
	return render(request, "personal/home.html", context)


def _landing_stats():
	"""Chiffres réels de la plateforme, pour la landing page.

	Remplace les chiffres décoratifs qui figuraient en dur dans le template
	(« 12+ fonctionnalités », « 100 % gratuit ») : ils n'apprenaient rien au
	visiteur. Un compteur n'est affiché que s'il dépasse un seuil crédible —
	afficher « 3 membres » desservirait la plateforme.

	Mis en cache 10 minutes : la landing est la page la plus exposée du site
	et ces agrégats n'ont pas besoin d'être calculés à chaque visite.
	"""
	from django.core.cache import cache

	cached = cache.get('landing_stats')
	if cached is not None:
		return cached

	from account.models import Account
	from post.models import Post
	from bazar.models import Annonce
	from group.models import Group
	from tourisme.models import LieuTouristique

	def _fmt(n):
		"""1 234 -> « 1.2 k », pour rester lisible sans mentir sur le chiffre."""
		if n >= 1000:
			return f"{n / 1000:.1f}".rstrip('0').rstrip('.') + ' k'
		return str(n)

	raw = {
		'membres':  Account.objects.filter(is_active=True).count(),
		'posts':    Post.objects.filter(status='published').count(),
		'annonces': Annonce.objects.filter(status='active').count(),
		'groupes':  Group.objects.count(),
		'lieux':    LieuTouristique.objects.count(),
	}

	# Seuil minimal en dessous duquel un compteur n'est pas montré.
	seuils = {'membres': 10, 'posts': 20, 'annonces': 5, 'groupes': 3, 'lieux': 3}
	labels = {
		'membres':  'Membres',
		'posts':    'Publications',
		'annonces': 'Annonces au Bazar',
		'groupes':  'Groupes',
		'lieux':    'Lieux à découvrir',
	}

	stats = [
		{'valeur': _fmt(raw[k]), 'label': labels[k]}
		for k in ('membres', 'posts', 'annonces', 'groupes', 'lieux')
		if raw[k] >= seuils[k]
	]

	cache.set('landing_stats', stats, 600)
	return stats


def landing_view(request):
	"""
	Vue de la landing page publique.
	Les utilisateurs connectés sont redirigés directement vers le feed (mobile-first).
	"""
	if request.user.is_authenticated:
		from django.shortcuts import redirect
		return redirect('post:post-view')

	now = timezone.now()

	announcements = Announcement.objects.filter(
		is_active=True,
		start_date__lte=now,
	).filter(
		models.Q(end_date__isnull=True) | models.Q(end_date__gte=now)
	).order_by('-start_date')

	hero = HeroSettings.get()

	# NOTE : les aperçus « dernières annonces » et « lieux à découvrir » ont été
	# retirés avec la refonte de la page — la maquette retenue les remplace par
	# les quatre piliers, qui renvoient vers les sections elles-mêmes. Les
	# requêtes correspondantes ont disparu avec eux plutôt que de rester
	# exécutées pour rien à chaque visite.

	context = {
		'announcements': announcements,
		'page_title': 'Vazimba — le réseau social malgache',
		'meta_description': (
			"Vazimba réunit la communauté malgache : fil d'actualité, stories, "
			"Bazar pour acheter et vendre, groupes, lives et découverte du pays. "
			"Gratuit, en français et en malgache."
		),
		'hero': hero,
		'stats': _landing_stats(),
	}
	return render(request, "personal/landing.html", context)


def privacy_policy_view(request):
    """Politique de confidentialité — obligatoire pour Google Play Store."""
    return render(request, "personal/privacy_policy.html")
