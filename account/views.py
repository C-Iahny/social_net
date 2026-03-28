from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import login, authenticate, logout
from django.conf import settings

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

	posts = Post.objects.filter(author=account).order_by("-id")

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
		context['post_count'] = posts.count()
		# Posts with images (for the Photos tab)
		context['photos'] = posts.exclude(header_image='').exclude(header_image__isnull=True)
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
	context = {}
	if request.method == "GET":
		search_query = request.GET.get("q")
		if len(search_query) > 0:
			search_results = Account.objects.filter(username__icontains=search_query).distinct()#.filter(email__icontains=search_query) <== à mettre devant le 1er filter normalement.
			user = request.user
			accounts = [] # [(account1, True), (account2, False), ...]
			for account in search_results:
				accounts.append((account, False)) # you have no friends yet
			context['accounts'] = accounts
				
	return render(request, "account/search_results.html", context)


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
			# delete the old profile image so the name is preserved.
			#account.profile_image.delete() # ilay contraire foana no mahazo anah fa io ny form tena tokony ho izy.
			form.save()
			return redirect("account:view", user_id=account.pk)
		else:
			form = AccountUpdateForm(request.POST, instance=request.user,
				initial={
					"id":            account.pk,
					"email":         account.email,
					"username":      account.username,
					"profile_image": account.profile_image,
					"hide_email":    account.hide_email,
					"bio":           account.bio,
					"location":      account.location,
				}
			)
			context['form'] = form
	else:
		form = AccountUpdateForm(
			initial={
					"id":            account.pk,
					"email":         account.email,
					"username":      account.username,
					"profile_image": account.profile_image,
					"hide_email":    account.hide_email,
					"bio":           account.bio,
					"location":      account.location,
				}
			)
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

			# delete the old image
			user.profile_image.delete()

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














