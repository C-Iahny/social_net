from django.db import models
from django.conf import settings
from django.utils import timezone


# ──────────────────────────────────────────────────────────────
# Singleton : réglages de la section Hero (page Explore)
# ──────────────────────────────────────────────────────────────
class HeroSettings(models.Model):
    title         = models.CharField(
        max_length=200,
        default="Explorez la communauté ZOOT",
        verbose_name="Titre principal (H1)",
    )
    subtitle      = models.TextField(
        default="Découvrez des publications, des personnes et des contenus du monde entier. Connectez-vous, partagez et inspirez-vous.",
        verbose_name="Texte d'accroche",
    )
    gradient_from = models.CharField(
        max_length=20,
        default="#1877f2",
        verbose_name="Couleur de début (dégradé)",
        help_text="Code couleur hexadécimal, ex. #1877f2",
    )
    gradient_to   = models.CharField(
        max_length=20,
        default="#7c3aed",
        verbose_name="Couleur de fin (dégradé)",
        help_text="Code couleur hexadécimal, ex. #7c3aed",
    )
    background_image = models.ImageField(
        upload_to="hero_bg/",
        blank=True,
        null=True,
        verbose_name="Image de fond (optionnel)",
        help_text="Si renseignée, s'affiche derrière le dégradé (qui devient un calque semi-transparent).",
    )

    class Meta:
        verbose_name        = "Réglages du Hero"
        verbose_name_plural = "Réglages du Hero"

    def __str__(self):
        return "Réglages du Hero"

    # Singleton : toujours pk=1
    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    # Ne peut pas être supprimé depuis l'admin
    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get(cls):
        """Retourne l'unique instance, en la créant si besoin."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Announcement(models.Model):
    PRIORITY_CHOICES = [
        ('info',    '🔵 Info'),
        ('success', '🟢 Succès'),
        ('warning', '🟡 Avertissement'),
        ('danger',  '🔴 Urgent'),
    ]

    title       = models.CharField(max_length=200, verbose_name="Titre")
    content     = models.TextField(verbose_name="Contenu")
    priority    = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='info', verbose_name="Type")
    start_date  = models.DateTimeField(default=timezone.now, verbose_name="Date de début")
    end_date    = models.DateTimeField(null=True, blank=True, verbose_name="Date de fin (optionnel)")
    is_active   = models.BooleanField(default=True, verbose_name="Actif")
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = "Annonce"
        verbose_name_plural = "Annonces"

    def __str__(self):
        return f"[{self.get_priority_display()}] {self.title}"

    def is_visible(self):
        """Retourne True si l'annonce est active et dans sa période de diffusion."""
        now = timezone.now()
        if not self.is_active:
            return False
        if self.start_date > now:
            return False
        if self.end_date and self.end_date < now:
            return False
        return True


class PublicChatRoom(models.Model):

	# Room title
	title 				= models.CharField(max_length=255, unique=True, blank=False,)

	# all users who are authenticated and viewing the chat
	users 				= models.ManyToManyField(settings.AUTH_USER_MODEL, help_text="users who are connected to chat room.")

	def __str__(self):
		return self.title


	def connect_user(self, user):
		"""
		return true if user is added to the users list
		"""
		is_user_added = False
		if not user in self.users.all():
			self.users.add(user)
			self.save()
			is_user_added = True
		elif user in self.users.all():
			is_user_added = True
		return is_user_added 


	def disconnect_user(self, user):
		"""
		return true if user is removed from the users list
		"""
		is_user_removed = False
		if user in self.users.all():
			self.users.remove(user)
			self.save()
			is_user_removed = True
		return is_user_removed 


	@property
	def group_name(self):
		"""
		Returns the Channels Group name that sockets should subscribe to to get sent
		messages as they are generated.
		"""
		return "PublicChatRoom-%s" % self.id


class PublicRoomChatMessageManager(models.Manager):
    def by_room(self, room):
        qs = PublicRoomChatMessage.objects.filter(room=room).order_by("-timestamp")
        return qs

class PublicRoomChatMessage(models.Model):
    """
    Chat message created by a user inside a PublicChatRoom
    """
    user                = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    room                = models.ForeignKey(PublicChatRoom, on_delete=models.CASCADE)
    timestamp           = models.DateTimeField(auto_now_add=True)
    content             = models.TextField(unique=False, blank=False,)

    objects = PublicRoomChatMessageManager()

    def __str__(self):
        return self.content
















