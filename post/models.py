from django.db import models
from django.urls import reverse
from datetime import datetime, date
from ckeditor.fields import RichTextField
import uuid

from account.models import Account
from ZOOT.storage import AutoMediaCloudinaryStorage


class Category(models.Model):
    name = models.CharField(max_length=255)
    img = models.ImageField(upload_to='cat_images/')

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        #return reverse('article-detail', args=[str(self.id)] )
        return reverse('home')



#======================== POST ==================================

class Post(models.Model):
    #id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    title = models.CharField(max_length=255)
    header_image = models.ImageField(blank=True, null=True, upload_to="header_images")
    author = models.ForeignKey(Account, on_delete=models.CASCADE)
    body = RichTextField(blank=True, null=True) # as a caption
    snippet = models.CharField(max_length=255, blank=True, null=False, default='click the link above.')
    post_date = models.DateField(auto_now_add=True)
    category = models.CharField(max_length=255, blank=True, null=True, default='Category')
    likes = models.ManyToManyField(Account, related_name='like_number', blank=True, default=0)
    file  = models.FileField(blank=True, null=True, upload_to="files/")
    video = models.FileField(blank=True, null=True, upload_to="videos/")

    # Extensions vidéo reconnues
    VIDEO_EXTS = {'mp4', 'webm', 'ogg', 'mov', 'mkv', 'avi', 'm4v', '3gp'}

    @property
    def is_video(self):
        """Retourne True si le champ `video` contient un fichier vidéo."""
        if self.video and self.video.name:
            ext = self.video.name.rsplit('.', 1)[-1].lower() if '.' in self.video.name else ''
            return ext in self.VIDEO_EXTS
        return False

    @property
    def file_is_video(self):
        """Retourne True si le champ `file` est en réalité une vidéo."""
        if self.file and self.file.name:
            ext = self.file.name.rsplit('.', 1)[-1].lower() if '.' in self.file.name else ''
            return ext in self.VIDEO_EXTS
        return False

    def total_likes(self):
        return self.likes.count()

    @property
    def header_image_url(self):
        """Returns the header image URL via Cloudinary (resource_type='image'), or None."""
        if not self.header_image or not self.header_image.name:
            return None
        try:
            import cloudinary
            resource = cloudinary.CloudinaryResource(
                self.header_image.name,
                default_resource_type='image',
            )
            return resource.url
        except Exception:
            try:
                return self.header_image.url
            except Exception:
                return None

    def __str__(self):
        return self.title + ' posted by ' + str(self.author)


    def get_absolute_url(self):
        return reverse('post:post-detail', args=[self.pk])



#======================= POST END =================================

#======================= COMMENTAIRE ==================================

class Comment(models.Model):
    post       = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author     = models.ForeignKey(Account, on_delete=models.CASCADE)
    body       = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    parent     = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='replies'
    )

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.author} → {self.post} : {self.body[:40]}"

#======================= COMMENTAIRE END ==============================


#======================= REACTIONS ====================================

class Reaction(models.Model):
    REACTION_CHOICES = [
        ('like',  '👍'),
        ('heart', '❤️'),
        ('laugh', '😂'),
        ('wow',   '😮'),
        ('sad',   '😢'),
    ]
    EMOJI_MAP = {
        'like':  '👍',
        'heart': '❤️',
        'laugh': '😂',
        'wow':   '😮',
        'sad':   '😢',
    }

    post          = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reactions')
    user          = models.ForeignKey(Account, on_delete=models.CASCADE)
    reaction_type = models.CharField(max_length=10, choices=REACTION_CHOICES, default='like')
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'user')
        ordering        = ['created_at']

    def __str__(self):
        return f"{self.user} → {self.EMOJI_MAP.get(self.reaction_type, '?')} on {self.post}"

#======================= REACTIONS END ================================


#======================= POST MEDIA ===================================

class PostMedia(models.Model):
    """Fichiers multiples attachés à un post (images + vidéos mélangés)."""
    IMAGE = 'image'
    VIDEO = 'video'
    TYPE_CHOICES = [(IMAGE, 'Image'), (VIDEO, 'Vidéo')]

    VIDEO_EXTS = {'mp4', 'webm', 'ogg', 'mov', 'mkv', 'avi', 'm4v', '3gp'}

    post       = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='media_files')
    file       = models.FileField(upload_to='post_media/', storage=AutoMediaCloudinaryStorage())
    media_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=IMAGE)
    order      = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    @property
    def url(self):
        """
        Génère l'URL Cloudinary en utilisant le bon resource_type.
        Cloudinary stocke le public_id sans extension (ex. 'post_media/myvideo').
        On se base sur media_type (pas sur l'extension) pour distinguer
        '/image/upload/...' de '/video/upload/...'.
        """
        if not self.file or not self.file.name:
            return None
        try:
            import cloudinary
            cloudinary_rt = 'video' if self.media_type == self.VIDEO else 'image'
            resource = cloudinary.CloudinaryResource(
                self.file.name,
                default_resource_type=cloudinary_rt,
            )
            return resource.url
        except Exception:
            # Fallback : URL brute du backend de stockage
            return self.file.url

    @property
    def is_video(self):
        return self.media_type == self.VIDEO

    def __str__(self):
        return f"{self.media_type} #{self.order} → {self.post}"

#======================= POST MEDIA END ===============================


class Follow(models.Model):
    user            = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='follower')
    user_follower   = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='be_followed')

    def __str__(self):
        return f"{self.user} is following {self.user_follower}"




class Continent(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Country(models.Model):
    name = models.CharField(max_length=255)
    continent = models.ForeignKey(Continent, on_delete=models.CASCADE)

    def __str__(self):
        return self.name 










