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
	logger.debug("destination: %s", destination)

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
	"""
	- Logic here is kind of tricky
		is_self
		is_friend
			-1: NO_REQUEST_SENT
			0: THEM_SENT_TO_YOU
			1: YOU_SENT_TO_THEM
	"""
	context = {}
	user_id = kwargs.get("user_id")
#	try:

	try:
		account = Account.objects.get(pk=user_id)
	except Account.DoesNotExist:
		return HttpResponse("Utilisateur introuvable.", status=404)

	# First page only — infinite scroll loads the rest via profile_posts_more
	all_posts_qs = Post.objects.filter(author=account).order_by("-id").select_related('author')
	paginator   = Paginator(all_posts_qs, 6)
	first_page  = paginator.get_page(1)
	posts = list(first_page)

	# Enrich posts with reactions + threaded comments (same as feed)
	from django.db.models import Count
	post_ids = [p.id for p in posts]
	if post_ids:
		# Reaction counts per post (grouped)
		reactions_qs = (
			ReactionModel.objects.filter(post_id__in=post_ids)
			.values('post_id', 'reaction_type')
			.annotate(c=Count('id'))
		)
		reactions_by_post = {}
		for row in reactions_qs:
			reactions_by_post.setdefault(row['post_id'], {})[row['reaction_type']] = row['c']

		# Current user's reaction per post
		user_reaction_by_post = {}
		if request.user.is_authenticated:
			user_reactions_qs = ReactionModel.objects.filter(
				post_id__in=post_ids, user=request.user
			).values_list('post_id', 'reaction_type')
			user_reaction_by_post = {pid: rtype for pid, rtype in user_reactions_qs}

		# Comments (threaded)
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

	# Follow stats (Account IS the user model — use account.id directly)
	try:
		following = Follow.objects.filter(user=account.id)
		followers  = Follow.objects.filter(user_follower=account.id)
	except Exception:
		following = Follow.objects.none()
		followers  = Follow.objects.none()

	try:
		checkFollow = followers.filter(user=Account.objects.get(pk=request.user.id))
		isFollowing = len(checkFollow) != 0
	except (Account.DoesNotExist, AttributeError):
		isFollowing = False


#	except:
#		return HttpResponse("Something went wrong.")



	if account:
		context['id'] = account.id
		context['username'] = account.username
		context['email'] = account.email
		context['profile_image'] = account.profile_image.url
		context['hide_email'] = account.hide_email
		context['bio'] = account.bio
		context['location'] = account.location
		context['date_joined'] = account.date_joined

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
		# Photos tab — combine header_image (legacy) + PostMedia images
		from collections import namedtuple
		PhotoItem = namedtuple('PhotoItem', ['url', 'title', 'post_id'])
		photo_list = []
		# Legacy header_image
		all_posts_for_photos = list(all_posts_qs)
		for p in all_posts_for_photos:
			if p.header_image and p.header_image.name:
				try:
					photo_list.append(PhotoItem(url=p.header_image.url, title=p.title, post_id=p.id))
				except Exception:
					pass
		# PostMedia images
		try:
			all_photo_post_ids = [p.id for p in all_posts_for_photos]
			media_images = PostMedia.objects.filter(
				post_id__in=all_photo_post_ids,
				media_type=PostMedia.IMAGE
			).select_related('post').order_by('-post__id', 'order')
			for m in media_images:
				try:
					media_url = m.url  # utilise la propriété (CloudinaryResource avec le bon resource_type)
					if media_url:
						photo_list.append(PhotoItem(url=media_url, title=m.post.title, post_id=m.post_id))
				except Exception:
					pass
		except Exception:
			pass
		context['photos'] = photo_list
		context['friends_posts'] = Post.objects.filter(author__in=list(friends)).order_by('-id')
	#	context = {
	#		'posts': Post.objects.filter(author=user_id).order_by('-id'),
	#		'following': following,
	#		'followers': followers,
	#		'isFollowing': isFollowing,
	#		'account': account,
#
	#	}

		# Define template variables
		is_self = True
		is_friend = False
		request_sent = FriendRequestStatus.NO_REQUEST_SENT.value # range: ENUM -> friend/friend_request_status.FriendRequestStatus
		friend_requests = None
		user = request.user



		if user.is_authenticated and user != account:
			is_self = False
			if friends.filter(pk=user.id):
				is_friend = True
			else:
				is_friend = False
				# CASE1: Request has been sent from THEM to YOU: FriendRequestStatus.THEM_SENT_TO_YOU
				if get_friend_request_or_false(sender=account, receiver=user) != False:
					request_sent = FriendRequestStatus.THEM_SENT_TO_YOU.value
					context['pending_friend_request_id'] = get_friend_request_or_false(sender=account, receiver=user).id
				# CASE2: Request has been sent from YOU to THEM: FriendRequestStatus.YOU_SENT_TO_THEM
				elif get_friend_request_or_false(sender=user, receiver=account) != False:
					request_sent = FriendRequestStatus.YOU_SENT_TO_THEM.value
				# CASE3: No request sent from YOU or THEM: FriendRequestStatus.NO_REQUEST_SENT
				else:
					request_sent = FriendRequestStatus.NO_REQUEST_SENT.value
		
		elif not user.is_authenticated:
			is_self = False
		else:
			try:
				friend_requests = FriendRequest.objects.filter(receiver=user, is_active=True)
			except FriendRequest.DoesNotExist:
				pass

		# Set the template variables to the values
		context['is_self'] = is_self
		context['is_friend'] = is_friend
		context['request_sent'] = request_sent
		context['friend_requests'] = friend_requests
		context['BASE_URL'] = settings.BASE_URL

		return render(request, "account/account.html", context)


def account_search_view(request, *args, **kwargs):
    """Recherche globale : utilisateurs + posts + hashtags."""
    from django.db.models import Q, Count
    import re

    context = {}
    search_query = (request.GET.get('q') or '').strip()

    if search_query:
        # ── Utilisateurs ──────────────────────────────────────────────────────
        search_results = Account.objects.filter(
            username__icontains=search_query
        ).distinct()[:20]

        user = request.user
        try:
            friend_list = FriendList.objects.get(user=user)
            friend_ids  = set(friend_list.friends.values_list('id', flat=True))
        except (FriendList.DoesNotExist, AttributeError):
            friend_ids = set()

        accounts = []
        for acc in search_results:
            accounts.append((acc, acc.id in friend_ids))
        context['accounts'] = accounts

        # ── Posts ─────────────────────────────────────────────────────────────
        from post.models import Post
        posts = Post.objects.filter(
            Q(title__icontains=search_query) | Q(body__icontains=search_query)
        ).select_related('author').order_by('-id')[:10]
        context['posts'] = posts

        # ── Hashtags ──────────────────────────────────────────────────────────
        tag_query = search_query.lstrip('#').lower()
        from post.models import Post as PostModel
        matching_posts = PostModel.objects.filter(
            Q(body__icontains='#' + tag_query) | Q(title__icontains='#' + tag_query)
        ).values_list('body', 'title')

        pattern = re.compile(r'#(' + re.escape(tag_query) + r'[a-zA-ZÀ-ÿ0-9_]*)', re.I)
        tag_counts = {}
        for body, title in matching_posts:
            text = re.sub(r'<[^>]+>', ' ', (body or '') + ' ' + (title or ''))
            for t in pattern.findall(text):
                k = t.lower()
                tag_counts[k] = tag_counts.get(k, 0) + 1
        hashtags = [
            {'tag': '#' + t, 'count': c}
            for t, c in sorted(tag_counts.items(), key=lambda x: -x[1])[:8]
        ]
        context['hashtags'] = hashtags
        context['query'] = search_query
        context['total'] = len(accounts) + len(list(posts)) + len(hashtags)

    return render(request, "account/search_results.html", context)


def global_search_api(request):
    """API JSON pour le live-search du header (suggestions rapides)."""
    from django.db.models import Q
    from post.models import Post
    import re

    q = (request.GET.get('q') or '').strip()
    if len(q) < 2:
        return JsonResponse({'users': [], 'posts': [], 'hashtags': []})

    # Users
    users = Account.objects.filter(username__istartswith=q).values(
        'id', 'username', 'profile_image'
    )[:5]
    users_data = [
        {
            'id':       u['id'],
            'username': u['username'],
            'avatar':   u['profile_image'] if u['profile_image'] else '',
        }
        for u in users
    ]

    # Posts
    posts_qs = Post.objects.filter(
        Q(title__icontains=q)
    ).values('id', 'title', 'author__username')[:4]
    posts_data = [
        {'id': p['id'], 'title': p['title'], 'author': p['author__username']}
        for p in posts_qs
    ]

    # Hashtags
    tag_clean = q.lstrip('#').lower()
    matching = Post.objects.filter(
        Q(body__icontains='#' + tag_clean) | Q(title__icontains='#' + tag_clean)
    ).values_list('body', 'title')[:30]
    pattern = re.compile(r'#(' + re.escape(tag_clean) + r'[a-zA-ZÀ-ÿ0-9_]*)', re.I)
    tag_counts = {}
    for body, title in matching:
        text = re.sub(r'<[^>]+>', ' ', (body or '') + ' ' + (title or ''))
        for t in pattern.findall(text):
            k = t.lower()
            tag_counts[k] = tag_counts.get(k, 0) + 1
    hashtags = [
        {'tag': '#' + t, 'count': c}
        for t, c in sorted(tag_counts.items(), key=lambda x: -x[1])[:4]
    ]

    return JsonResponse({'users': users_data, 'posts': posts_data, 'hashtags': hashtags})


def edit_account_view(request, *args, **kwargs):
	if not request.user.is_authenticated:
		return redirect("login")
	user_id = kwargs.get("user_id")
	account = Account.objects.get(pk=user_id)
	if account.pk != request.user.pk:
		return HttpResponse("You cannot edit someone elses profile.")
	context = {}
	if request.POST:
		form = AccountUpdateForm(request.POST, request.FILES, instance=request.user)
		if form.is_valid():
			form.save()
			return redirect("account:view", user_id=account.pk)
	else:
		form = AccountUpdateForm(instance=request.user)
	context['form'] = form
	context['DATA_UPLOAD_MAX_MEMORY_SIZE'] = settings.DATA_UPLOAD_MAX_MEMORY_SIZE
	return render(request, "account/edit_account.html", context)


def save_temp_profile_image_from_base64String(imageString, user):
	INCORRECT_PADDING_EXCEPTION = "Incorrect padding"
	try:
		# os.makedirs crée tous les dossiers parents si nécessaire (important sur Railway)
		os.makedirs(settings.TEMP + "/" + str(user.pk), exist_ok=True)
		url = os.path.join(settings.TEMP + "/" + str(user.pk),TEMP_PROFILE_IMAGE_NAME)
		storage = FileSystemStorage(location=url)
		image = base64.b64decode(imageString)
		with storage.open('', 'wb+') as destination:
			destination.write(image)
			destination.close()
		return url
	except Exception as e:
		logger.warning("save_temp_profile_image exception: %s", e)
		# workaround for an issue I found
		if str(e) == INCORRECT_PADDING_EXCEPTION:
			imageString += "=" * ((4 - len(imageString) % 4) % 4)
			return save_temp_profile_image_from_base64String(imageString, user)
	return None






def profile_posts_more(request, *args, **kwargs):
	"""AJAX endpoint — returns a fragment of paginated profile posts (infinite scroll)."""
	from django.db.models import Count
	user_id = kwargs.get("user_id")
	try:
		account = Account.objects.get(pk=user_id)
	except Account.DoesNotExist:
		return JsonResponse({'html': '', 'has_next': False, 'next_page': None})

	page_number = request.GET.get('page', 2)
	all_posts_qs = Post.objects.filter(author=account).order_by("-id").select_related('author')
	paginator   = Paginator(all_posts_qs, 6)
	posts_page  = paginator.get_page(page_number)
	posts       = list(posts_page)

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

	html = render_to_string(
		'post/post_cards_fragment.html',
		{'posts_of_the_page': posts_page, 'request': request},
		request=request
	)
	return JsonResponse({
		'html':      html,
		'has_next':  posts_page.has_next(),
		'next_page': posts_page.next_page_number() if posts_page.has_next() else None,
	})


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
			if cropX < 0:
				cropX = 0
			if cropY < 0: # There is a bug with cropperjs. y can be negative.
				cropY = 0
			crop_img = img.crop((cropX, cropY, cropX + cropWidth, cropY + cropHeight))

			crop_img.save(url)

			# delete the old image (best-effort -- may fail if stored on Cloudinary with a legacy local path)
			try:
				user.profile_image.delete()
			except Exception:
				pass

			# Save the cropped image to user model
			with open(url, 'rb') as image_file:
				user.profile_image.save("profile_image.png", files.File(image_file))
			user.save()

			payload['result'] = "success"
			payload['cropped_profile_image'] = user.profile_image.url

			# delete temp file
			os.remove(url)
			
		except Exception as e:
			logger.error("crop_image exception: %s", e)
			payload['result'] = "error"
			payload['exception'] = str(e)
	return HttpResponse(json.dumps(payload), content_type="application/json")














