from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from datetime import datetime, date 
from ckeditor.fields import RichTextField

from account.models import Account


class Category(models.Model):
    name = models.CharField(max_length=255)
    img = models.ImageField(upload_to='cat_images/')

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        #return reverse('article-detail', args=[str(self.id)] )
        return reverse('home')



class Post(models.Model):
    title = models.CharField(max_length=255)
    header_image = models.ImageField(blank=True, null=True, upload_to="header_images")
    author = models.ForeignKey(Account, on_delete=models.CASCADE)
    body = RichTextField(blank=True, null=True)
    snippet = models.CharField(max_length=255, default='click the link above.')
    post_date = models.DateField(auto_now_add=True)
    category = models.CharField(max_length=255, default='Category')
    likes = models.ManyToManyField(Account, related_name='mksd_event', blank=True)
    file = models.FileField(blank=True, null=True, upload_to="files/")

    def total_likes(self):
        return self.likes.count()


    def __str__(self):
        return self.title + ' | ' + str(self.author)

    def get_absolute_url(self):
        return reverse('article-detail', args=[str(self.id)] )



class Continent(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Country(models.Model):
    name = models.CharField(max_length=255)
    continent = models.ForeignKey(Continent, on_delete=models.CASCADE)

    def __str__(self):
        return self.name 










