from django.db import models
from django.urls import reverse
from datetime import datetime, date 
from ckeditor.fields import RichTextField
import uuid

from account.models import Account


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


    def __str__(self):
        return self.title + ' posted by ' + str(self.author)


    def get_absolute_url(self):
        return reverse('post:post-view')



#======================= POST END =================================

#======================= COMMENTAIRE ==================================

class Comment(models.Model):
    post       = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author     = models.ForeignKey(Account, on_delete=models.CASCADE)
    body       = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.author} → {self.post} : {self.body[:40]}"

#======================= COMMENTAIRE END ==============================


class Follow(models.Model):
    user            = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='follower')
    user_follower   = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='be_follwed')

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










