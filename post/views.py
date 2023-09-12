from django.shortcuts import render
from django.shortcuts import render, redirect
from django.contrib.auth.models import User, auth
from django.contrib import messages
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView, DeleteView, UpdateView, CreateView, ListView, DetailView
from django.contrib.auth import get_user_model

from itertools import chain
import random

User = get_user_model()

from account.models import Account
from .forms import PostForm
from .models import  Post, Continent, Country
from friend.models import FriendList







def Index(request):

	continent = Continent.objects.all()
	countries = Country.objects.all()

	context = {
		'continent': continent,
		'countries': countries,
	}
	return render(request, "post/index.html", context)


class Post_view(TemplateView):

	def get(self, request, *args, **kwargs):

		posts = Post.objects.all().order_by('-id')
		user = Account.objects.all()
		friends_list = FriendList.objects.get(user=request.user.id)
		friends = friends_list.friends.all()


		#form = PostForm()

		context = {
			'friends': friends,
			'posts': Post.objects.filter(author__in=list(friends) + [request.user]).order_by('-id')
		}

		return render(request, "post/post_view.html", context)

"""	def post(self, request, *args, **kwargs):

		posts = Post.objects.all().order_by('-id')
		user = Account.objects.all()
		form = PostForm(request.POST)

		if form.valid():
			new_post = form.save(commit=False)
			new_post.author = request.user
			new_post.save()

		context = {
			'posts': posts,
			'user': user,
			'form': form, 
		}

		return render(request, "post/post_view.html", context)"""














def like_post(request):
	username = request.user.username
	post_id = request.GET.get('post_id')

	post = Post.objects.get(id=post_id)

	like_filter = LikePost.objects.filter(post_id=post_id, username=username).first()

	if like_filter == None:
		new_like = LikePost.objects.create(post_id=post_id, username=username)
		new_like.save()
		post.no_of_likes = post.no_of_likes+1
		post.save()
		return redirect('/')
	else:
		like_filter.delete()
		post.no_of_likes = post.no_of_likes-1
		post.save()
		return redirect('/')














