from django.db import models
from functools import cached_property
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.core.files.storage import FileSystemStorage
from django.db.models.fields.files import ImageFieldFile, ImageField
from django.conf import settings
import os
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
import uuid

from friend.models import FriendList
from django.contrib.auth import get_user_model


class ProfileImageFieldFile(ImageFieldFile):
    """ImageFieldFile qui retourne l'image statique par défaut si aucune photo n'est définie."""
    @property
    def url(self):
        from django.templatetags.static import static
        _default = static('images/profile_pic.png')
        name = str(self.name) if self.name else ''
        if not name or name == 'images/profile_pic.png':
            return _default
        try:
            from django.core.files.storage import FileSystemStorage
            # FileSystemStorage ne lève pas d'exception pour les fichiers manquants.
            # On vérifie l'existence physique pour éviter les 404.
            if isinstance(self.storage, FileSystemStorage):
                import os
                try:
                    full_path = self.storage.path(name)
                    if not os.path.exists(full_path):
                        return _default
                except Exception:
                    return _default
            return super().url
        except Exception:
            return _default


class ProfileImageField(ImageField):
    attr_class = ProfileImageFieldFile


class MyAccountManager(BaseUserManager):
	def create_user(self, email, username, password=None):
		if not email:
			raise ValueError('Users must have an email address')
		if not username:
			raise ValueError('Users must have a username')

		user = self.model(
			email=self.normalize_email(email),
			username=username,
		)

		user.set_password(password)
		user.save(using=self._db)
		return user

	def create_superuser(self, email, username, password):
		user = self.create_user(
			email=self.normalize_email(email),
			password=password,
			username=username,
		)
		user.is_admin = True
		user.is_staff = True
		user.is_superuser = True
		user.save(using=self._db)
		return user


def get_profile_image_filepath(self, filename):
	return f'profile_images/' + str(self.pk) + '/profile_image.png'

def get_default_profile_image():
	return "images/profile_pic.png"


class Account(AbstractBaseUser):
	email 					= models.EmailField(verbose_name="email", max_length=60, unique=True)
	username 				= models.CharField(max_length=30, unique=True)
	date_joined				= models.DateTimeField(verbose_name='date joined', auto_now_add=True)
	last_login				= models.DateTimeField(verbose_name='last login', auto_now=True)
	is_admin				= models.BooleanField(default=False)
	is_active				= models.BooleanField(default=True)
	is_staff				= models.BooleanField(default=False)
	is_superuser			= models.BooleanField(default=False)
	profile_image			= ProfileImageField(max_length=255, upload_to=get_profile_image_filepath, null=True, blank=True, default=get_default_profile_image)
	hide_email				= models.BooleanField(default=True)
	cover_image				= models.ImageField(
		upload_to='cover_images/',
		null=True, blank=True,
	)
# From Tomi -----------------------------------------------
	bio = models.TextField(blank=True)
	location = models.CharField(max_length=100, blank=True)
	region = models.CharField(
		max_length=30, blank=True, default='',
		verbose_name='Région',
		help_text='Région de Madagascar (pour le filtre "Près de chez moi")',
		db_index=True,
	)
	cgu_accepted_at = models.DateTimeField(
		null=True, blank=True,
		verbose_name="CGU & confidentialité acceptées le"
	)
# ── Téléphone ─────────────────────────────────────────────
	phone_number = models.CharField(
		max_length=20, blank=True, default='',
		verbose_name='Numéro de téléphone',
		help_text='Format international : +261 34 XX XXX XX',
		db_index=True,
	)
	phone_verified = models.BooleanField(
		default=False,
		verbose_name='Téléphone vérifié',
		help_text='Le numéro a été confirmé par SMS.',
	)
# ---------------------------------------------------------
	USERNAME_FIELD = 'email'
	REQUIRED_FIELDS = ['username']

	objects = MyAccountManager()

	def __str__(self):
		return self.username

	def get_profile_image_filename(self):
		from pathlib import PurePosixPath
		image_path = str(self.profile_image)
		prefix = f'profile_images/{self.pk}/'
		try:
			idx = image_path.index(prefix)
			return image_path[idx:]
		except ValueError:
			return image_path

	def has_perm(self, perm, obj=None):
		return self.is_admin

	def has_module_perms(self, app_label):
		return True

	@cached_property
	def score_fihavanana(self):
		"""Score de solidarité communautaire (Fihavanana).
		Calculé en une passe SQL par instance — mis en cache pour la durée de la requête
		(cached_property évite de recalculer si le template l'appelle plusieurs fois).
		"""
		try:
			from django.db.models import Case, When, IntegerField, Sum
			from post.models import Post, Comment, Reaction, Repost
			from friend.models import FriendList

			# Posts publiés : +10 par Kabary, +5 par post standard — une seule requête SQL
			post_score = Post.objects.filter(author=self).aggregate(
				s=Sum(Case(
					When(post_type='kabary', then=10),
					default=5,
					output_field=IntegerField(),
				))
			)['s'] or 0

			# Commentaires (+2), réactions reçues (+3) — 2 COUNT SQL
			comment_score  = Comment.objects.filter(author=self).count() * 2
			reaction_score = Reaction.objects.filter(post__author=self).count() * 3

			# Reposts (+4)
			try:
				repost_score = Repost.objects.filter(post__author=self).count() * 4
			except Exception:
				repost_score = 0

			# Amis (+3)
			try:
				fl = FriendList.objects.get(user=self)
				friend_score = fl.friends.count() * 3
			except Exception:
				friend_score = 0

			# Groupes (+2)
			try:
				from group.models import GroupMembership
				group_score = GroupMembership.objects.filter(user=self).count() * 2
			except Exception:
				group_score = 0

			total = post_score + comment_score + reaction_score + repost_score + friend_score + group_score
			return max(0, total)
		except Exception:
			return 0

	@property
	def fihavanana_level(self):
		"""Niveau Fihavanana basé sur le score."""
		score = self.score_fihavanana
		if score >= 500:
			return ('Mpitarika', '🌟', '#f59e0b')   # Leader
		elif score >= 200:
			return ('Mpiahy', '💛', '#10b981')       # Bienfaiteur
		elif score >= 80:
			return ('Mpiray tsipy', '💙', '#3b82f6') # Solidaire
		elif score >= 30:
			return ('Mpankafy', '💚', '#22c55e')     # Ami
		else:
			return ('Vahiny', '🤍', '#94a3b8')       # Visiteur


@receiver(post_save, sender=Account)
def user_save(sender, instance, **kwargs):
    FriendList.objects.get_or_create(user=instance)


# ─────────────────────────────────────────────────────────────────────────────
# Vérification OTP par SMS
# ─────────────────────────────────────────────────────────────────────────────
import random
import string

class PhoneVerification(models.Model):
    """Code OTP envoyé par SMS pour vérifier un numéro de téléphone."""

    user = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name='phone_verifications',
        verbose_name='Utilisateur',
    )
    phone = models.CharField(
        max_length=20,
        verbose_name='Numéro en cours de vérification',
        help_text='Format E.164 (+261XXXXXXXXX)',
    )
    code = models.CharField(
        max_length=6,
        verbose_name='Code OTP',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Créé le')
    attempts   = models.PositiveSmallIntegerField(default=0, verbose_name='Tentatives')
    verified   = models.BooleanField(default=False, verbose_name='Validé')

    class Meta:
        verbose_name = 'Vérification téléphone'
        verbose_name_plural = 'Vérifications téléphone'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} — {self.phone} ({"OK" if self.verified else "en attente"})'

    # Durée de validité en minutes
    OTP_VALID_MINUTES = 10
    # Max tentatives de saisie avant invalidation
    MAX_ATTEMPTS = 5
    # Max envois par numéro par heure
    MAX_SENDS_PER_HOUR = 3

    @classmethod
    def generate_code(cls):
        return ''.join(random.choices(string.digits, k=6))

    @property
    def is_expired(self):
        from django.utils import timezone
        from datetime import timedelta
        return timezone.now() > self.created_at + timedelta(minutes=self.OTP_VALID_MINUTES)
