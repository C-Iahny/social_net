from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import login, authenticate, logout
from django.conf import settings
from django.core.paginator import Paginator
from django.template.loader import render_to_string

from django.core.files.storage import default_storage
from django.core.files.storage import FileSystemStorage
import os
from PIL import Image
import json
import base64
import requests
import logging
from django.core import files

logger = logging.getLogger(__name__)


from account.forms import RegistrationForm, AccountAuthenticationForm, AccountUpdateForm
from account.models import Account
from friend.utils import get_friend_request_or_false
from friend.friend_request_status import FriendRequestStatus
from friend.models import FriendList, FriendRequest

from post.models import Post, Follow
from post.models import Comment as CommentModel, Reaction as ReactionModel, PostMedia
from post.views import _attach_media

TEMP_PROFILE_IMAGE_NAME = "temp_profile_image.png"


def register_view(request, *args, **kwargs):
	user = request.user
	if user.is_authenticated:
		return HttpResponse("You are already authenticated as " + str(user.email))

	context = {}
	if request.POST:
		form = RegistrationForm(request.POST)
		if form.is_valid():
			form.save()
			email = form.cleaned_data.get('email').lower()
			raw_password = form.cleaned_data.get('password1')
			account = authenticate(email=email, password=raw_password)
			login(request, account)
			destination = kwargs.get("next")
			if destination:
				return redirect(destination)
			return redirect('home')
		else:
			context['registration_form'] = form
	else:
		form = RegistrationForm()
		context['registration_form'] = form
	return render(request, 'account/register.html', context)


def login_view(request, *args, **kwargs):
	context = {}
	user = request.user
	if user.is_authenticated:
		return redirect("post:index")

	destination = get_redirect_if_exists(request)

	if request.POST:
		form = AccountAuthenticationForm(request.POST)
		if form.is_valid():
			email = request.POST['email']
			password = request.POST['password']
			user = authenticate(email=email, password=password)
			if user:
				login(request, user)
				if destination:
					return redirect(destination)
				return redirect("post:index")
	else:
		form = AccountAuthenticationForm()

	context['login_form'] = form
	return render(request, "account/login.html", context)


def logout_view(request):
	logout(request)
	return redirect("post:index")


def get_redirect_if_exists(request):
	redirect = None
	if request.GET:
		if request.GET.get("next"):
			redirect = str(request.GET.get("next"))
	return redirect


def account_view(request, *args, **kwargs):
	context = {}
	user_id = kwargs.get("user_id")

	try:
		account = Account.objects.get(pk=user_id)
	except Account.DoesNotExist:
		return HttpResponse("Utilisateur introuvable.", status=404)

	# Posts (first page)
	all_posts_qs = Post.objects.filter(author=account).order_by("-id").select_related('author')
	paginator   = Paginator(all_posts_qs, 6)
	first_page  = paginator.get_page(1)
	posts = list(first_page)

	# Enrich posts with reactions + threaded comments
	from django.db.models import Count
	post_ids = [p.id for p in posts]
	if post_ids:
		reactions_qs = (
			ReactionModel.objects.filter(post_id__in=post_ids)
			.values('post_id', 'reaction_type')
			.annotate(c=Count('id'))
		)
		reactions_by_post = {}
		for row in reactions_qs:
			reactions_by_post.setdefault(row['post_id'], {})[row['reaction_type']] = row['c']

		user_reaction_by_post = {}
		if request.user.is_authenticated:
			user_reactions_qs = ReactionModel.objects.filter(
				post_id__in=post_ids, user=request.user
			).values_list('post_id', 'reaction_type')
			user_reaction_by_post = {pid: rtype for pid, rtype in user_reactions_qs}

		comments_all = list(CommentModel.objects.filter(
			post_id__in=post_ids).select_related('author').order_by('created_at'))
		top_by_post = {}
		replies_map = {}
		for c in comments_all:
			if c.parent_id is None:
				top_by_post.setdefault(c.post_id, []).append(c)
			else:
				replies_map.setdefault(c.parent_id, []).append(c)
		for top_comments in top_by_post.values():
			for c in top_comments:
				c.reply_list = replies_map.get(c.id, [])

		for post in posts:
			post.user_reaction   = user_reaction_by_post.get(post.id)
			post.reaction_counts = reactions_by_post.get(post.id, {})
			post.total_reactions = sum(post.reaction_counts.values())
			top = top_by_post.get(post.id, [])
			for c in top:
				if not hasattr(c, 'reply_list'):
					c.reply_list = []
			post.page_comments  = top
			post.total_comments = len(top) + sum(len(c.reply_list) for c in top)
		_attach_media(posts, post_ids)
	else:
		for post in posts:
			post.user_reaction   = None
			post.reaction_counts = {}
			post.total_reactions = 0
			post.page_comments   = []
			post.total_comments  = 0
			post.media_list      = []

	if account:
		context['id'] = account.id
		context['username'] = account.username
		context['email'] = account.email
		context['profile_image'] = account.profile_image.url
		context['hide_email'] = account.hide_email
		context['bio'] = account.bio
		context['location'] = account.location
		context['date_joined'] = account.date_joined

		# Cover image
		cover_url = None
		if account.cover_image and account.cover_image.name:
			try:
				if isinstance(account.cover_image.storage, FileSystemStorage):
					try:
						if os.path.exists(account.cover_image.storage.path(account.cover_image.name)):
							cover_url = account.cover_image.url
					except Exception:
						pass
				else:
					cover_url = account.cover_image.url
			except Exception:
				pass
		context['cover_image_url'] = cover_url

		try:
			friend_list = FriendList.objects.get(user=account)
		except FriendList.DoesNotExist:
			friend_list = FriendList(user=account)
			friend_list.save()
		friends = friend_list.friends.all()
		context['friends'] = friends
		context['friends_count'] = friends.count()
		context['posts'] = posts
		context['post_count'] = all_posts_qs.count()
		context['posts_has_next'] = first_page.has_next()
		context['posts_next_page'] = 2 if first_page.has_next() else None

		# Photos tab
		from collections import namedtuple
		PhotoItem = namedtuple('PhotoItem', ['url', 'title', 'post_id'])
		photo_list = []
		for m in PostMedia.objects.filter(
			post__author=account, media_type='image'
		).select_related('post').order_by('-post__post_date')[:50]:
			media_url = m.url
			if media_url:
				photo_list.append(PhotoItem(url=media_url, title=m.post.title, post_id=m.post_id))

		context['photos'] = photo_list
		context['is_self'] = False
		context['is_friend'] = False
		context['request_sent'] = FriendRequestStatus.NO_REQUEST_SENT.value

		if request.user.is_authenticated:
			if request.user == account:
				context['is_self'] = True
				# Incoming friend requests for self
				try:
					friend_requests = FriendRequest.objects.filter(receiver=account, is_active=True)
					context['friend_requests'] = friend_requests
				except Exception:
					context['friend_requests'] = []
			else:
				context['is_friend'] = friends.filter(pk=request.user.pk).exists()
				request_sent = get_friend_request_or_false(account, request.user)
				if request_sent is False:
					context['request_sent'] = FriendRequestStatus.NO_REQUEST_SENT.value
					context['pending_friend_request_id'] = None
				else:
					context['request_sent'] = request_sent.status
					context['pending_friend_request_id'] = request_sent.id

	return render(request, 'account/account.html', context)


def account_search_view(request):
	context = {}
	query = request.GET.get('q', '').strip()
	context['query'] = query
	context['total'] = 0

	if query:
		from django.db.models import Q, Count
		from post.models import Hashtag

		# Users
		accounts_qs = Account.objects.filter(
			Q(username__icontains=query) | Q(email__icontains=query)
		).exclude(pk=request.user.pk if request.user.is_authenticated else 0)[:20]

		accounts_with_friend = []
		if request.user.is_authenticated:
			try:
				fl = FriendList.objects.get(user=request.user)
				friend_ids = set(fl.friends.values_list('id', flat=True))
			except FriendList.DoesNotExist:
				friend_ids = set()
			for acc in accounts_qs:
				accounts_with_friend.append((acc, acc.id in friend_ids))
		else:
			accounts_with_friend = [(acc, False) for acc in accounts_qs]

		# Posts
		posts_qs = Post.objects.filter(
			Q(title__icontains=query) | Q(body__icontains=query)
		).select_related('author')[:20]

		# Hashtags
		hashtags_qs = Hashtag.objects.filter(tag__icontains=query)[:10]

		context['accounts'] = accounts_with_friend
		context['posts'] = posts_qs
		context['hashtags'] = hashtags_qs
		context['total'] = len(accounts_with_friend) + posts_qs.count() + hashtags_qs.count()

	return render(request, 'account/search_results.html', context)


def edit_account_view(request, *args, **kwargs):
	if not request.user.is_authenticated:
		return redirect('login')
	user_id = kwargs.get('user_id')
	try:
		account = Account.objects.get(pk=user_id)
	except Account.DoesNotExist:
		return HttpResponse("Utilisateur introuvable.", status=404)
	if request.user != account:
		return HttpResponse("Vous ne pouvez pas modifier ce profil.", status=403)

	context = {}
	if request.POST:
		form = AccountUpdateForm(request.POST, request.FILES, instance=request.user)
		if form.is_valid():
			form.save()
			return redirect('account:view', user_id=account.id)
		else:
			context['form'] = form
	else:
		form = AccountUpdateForm(
			initial={
				'email':      account.email,
				'username':   account.username,
				'hide_email': account.hide_email,
				'bio':        account.bio,
				'location':   account.location,
			}
		)
	context['form'] = form
	context['DATA_UPLOAD_MAX_MEMORY_SIZE'] = settings.DATA_UPLOAD_MAX_MEMORY_SIZE
	return render(request, 'account/edit_account.html', context)


def save_temp_profile_image_from_base64String(imageString, user):
	INCORRECT_PADDING_EXCEPTION = "Incorrect padding"
	try:
		if not os.path.exists(settings.TEMP):
			os.makedirs(settings.TEMP)
		url = os.path.join(settings.TEMP, TEMP_PROFILE_IMAGE_NAME)
		storage = FileSystemStorage(location=settings.TEMP)
		image = base64.b64decode(imageString)
		with open(url, 'wb') as f:
			f.write(image)
		return url
	except Exception as e:
		raise Exception(str(e))


def crop_image(request, *args, **kwargs):
	payload = {}
	user = request.user
	if request.POST and user.is_authenticated:
		try:
			imageString = request.POST.get("image")
			url = save_temp_profile_image_from_base64String(imageString, user)
			img = Image.open(url)

			cropX = int(float(str(request.POST.get("cropX"))))
			cropY = int(float(str(request.POST.get("cropY"))))
			cropWidth = int(float(str(request.POST.get("cropWidth"))))
			cropHeight = int(float(str(request.POST.get("cropHeight"))))

			if cropX < 0: cropX = 0
			if cropY < 0: cropY = 0

			cropped_img = img.crop((cropX, cropY, cropX + cropWidth, cropY + cropHeight))
			cropped_img = cropped_img.resize((200, 200), Image.LANCZOS)
			cropped_img.save(url)

			user.profile_image.delete(save=False)

			user.profile_image.save(
				get_profile_image_filepath(user, url),
				files.File(open(url, 'rb')),
			)
			user.save()

			payload['result'] = 'success'
			payload['cropped_profile_image'] = user.profile_image.url
		except Exception as e:
			payload['result'] = 'error'
			payload['exception'] = str(e)
	return JsonResponse(payload)


def get_profile_image_filepath(user, filename):
	return f'profile_images/{user.pk}/profile_image.png'


def global_search_api(request):
	"""API endpoint for the header search bar (returns JSON)."""
	query = request.GET.get('q', '').strip()
	if not query or len(query) < 2:
		return JsonResponse({'results': []})

	from django.db.models import Q
	from post.models import Hashtag

	results = []

	# Users
	users = Account.objects.filter(
		Q(username__icontains=query)
	)[:5]
	for u in users:
		results.append({
			'type': 'user',
			'id': u.id,
			'label': u.username,
			'url': f'/account/{u.id}/',
			'avatar': u.profile_image.url,
		})

	# Hashtags
	hashtags = Hashtag.objects.filter(tag__icontains=query)[:3]
	for h in hashtags:
		results.append({
			'type': 'hashtag',
			'id': h.id,
			'label': h.tag,
			'url': f'/feed/hashtag/{h.tag.lstrip("#")}/',
		})

	# Posts
	posts = Post.objects.filter(
		Q(title__icontains=query) | Q(body__icontains=query)
	).select_related('author')[:5]
	for p in posts:
		results.append({
			'type': 'post',
			'id': p.id,
			'label': p.title or p.body[:60],
			'url': p.get_absolute_url(),
			'author': p.author.username,
		})

	return JsonResponse({'results': results})


def profile_posts_more(request, *args, **kwargs):
	"""API pour l'infinite scroll sur la page profil."""
	user_id = kwargs.get('user_id')
	try:
		account = Account.objects.get(pk=user_id)
	except Account.DoesNotExist:
		return JsonResponse({'posts_html': '', 'has_next': False})

	page_num = int(request.GET.get('page', 2))
	all_posts_qs = Post.objects.filter(author=account).order_by("-id").select_related('author')
	paginator = Paginator(all_posts_qs, 6)
	page = paginator.get_page(page_num)
	posts = list(page)

	# Enrich
	from django.db.models import Count
	post_ids = [p.id for p in posts]
	if post_ids:
		reactions_qs = (
			ReactionModel.objects.filter(post_id__in=post_ids)
			.values('post_id', 'reaction_type')
			.annotate(c=Count('id'))
		)
		reactions_by_post = {}
		for row in reactions_qs:
			reactions_by_post.setdefault(row['post_id'], {})[row['reaction_type']] = row['c']

		user_reaction_by_post = {}
		if request.user.is_authenticated:
			user_reactions_qs = ReactionModel.objects.filter(
				post_id__in=post_ids, user=request.user
			).values_list('post_id', 'reaction_type')
			user_reaction_by_post = {pid: rtype for pid, rtype in user_reactions_qs}

		comments_all = list(CommentModel.objects.filter(
			post_id__in=post_ids).select_related('author').order_by('created_at'))
		top_by_post = {}
		replies_map = {}
		for c in comments_all:
			if c.parent_id is None:
				top_by_post.setdefault(c.post_id, []).append(c)
			else:
				replies_map.setdefault(c.parent_id, []).append(c)
		for tc in top_by_post.values():
			for c in tc:
				c.reply_list = replies_map.get(c.id, [])
		for post in posts:
			post.user_reaction   = user_reaction_by_post.get(post.id)
			post.reaction_counts = reactions_by_post.get(post.id, {})
			post.total_reactions = sum(post.reaction_counts.values())
			top = top_by_post.get(post.id, [])
			for c in top:
				if not hasattr(c, 'reply_list'):
					c.reply_list = []
			post.page_comments  = top
			post.total_comments = len(top) + sum(len(c.reply_list) for c in top)
		_attach_media(posts, post_ids)
	else:
		for post in posts:
			post.user_reaction = None
			post.reaction_counts = {}
			post.total_reactions = 0
			post.page_comments = []
			post.total_comments = 0
			post.media_list = []

	posts_html = render_to_string(
		'post/post_cards_fragment.html',
		{'posts_of_the_page': posts, 'request': request},
		request=request,
	)
	return JsonResponse({
		'posts_html': posts_html,
		'has_next': page.has_next(),
		'next_page': page_num + 1 if page.has_next() else None,
	})


def update_cover_image(request):
	"""AJAX endpoint pour changer la photo de couverture."""
	if not request.user.is_authenticated:
		return JsonResponse({'error': 'Non authentifié.'}, status=401)
	if request.method != 'POST':
		return JsonResponse({'error': 'Méthode non autorisée.'}, status=405)

	cover_file = request.FILES.get('cover')
	if not cover_file:
		return JsonResponse({'error': 'Aucun fichier reçu.'}, status=400)

	allowed_mime = {
		'image/jpeg', 'image/jpg', 'image/png', 'image/webp',
		'image/gif', 'image/heic', 'image/heif', 'image/bmp', 'image/tiff',
	}
	mime = (cover_file.content_type or '').split(';')[0].strip().lower()
	if mime not in allowed_mime:
		return JsonResponse({'error': 'Format non supporté (jpeg, png, webp, gif, heic…).'}, status=400)

	if cover_file.size > 10 * 1024 * 1024:
		return JsonResponse({'error': 'Fichier trop volumineux (max 10 Mo).'}, status=400)

	try:
		import uuid
		ext = os.path.splitext(cover_file.name)[-1].lower() or '.jpg'
		filename = f"cover_images/{uuid.uuid4().hex}{ext}"
		cover_file.seek(0)
		account = request.user
		if account.cover_image and account.cover_image.name:
			try:
				account.cover_image.delete(save=False)
			except Exception:
				pass
		account.cover_image.save(filename, cover_file, save=True)
		url = account.cover_image.url
		return JsonResponse({'ok': True, 'url': url})
	except Exception as e:
		logger.exception("update_cover_image FAILED: %s", e)
		return JsonResponse({'error': f'Erreur upload : {e}'}, status=500)
