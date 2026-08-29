from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
import json

from account.models import Account
from friend.models import FriendRequest, FriendList


def _json(payload, status=200):
	return JsonResponse(payload, status=status)


@login_required(login_url='login')
@require_POST
def send_friend_request(request, *args, **kwargs):
	user = request.user
	user_id = request.POST.get("receiver_user_id")
	if not user_id:
		return _json({'response': "Unable to sent a friend request."}, status=400)

	try:
		receiver = Account.objects.get(pk=user_id)
	except (Account.DoesNotExist, ValueError):
		# Un identifiant inconnu ou non numérique levait une exception
		# non interceptée → erreur 500.
		return _json({'response': "That user does not exist."}, status=404)

	if receiver == user:
		return _json({'response': "You cannot send a friend request to yourself."}, status=400)

	already_sent = FriendRequest.objects.filter(
		sender=user, receiver=receiver, is_active=True
	).exists()
	if already_sent:
		return _json({'response': "You already sent them a friend request."})

	FriendRequest.objects.create(sender=user, receiver=receiver)
	return _json({'response': "Friend request sent."})


@login_required(login_url='login')
def friend_requests(request, *args, **kwargs):
	user = request.user
	user_id = kwargs.get("user_id")
	try:
		account = Account.objects.get(pk=user_id)
	except (Account.DoesNotExist, ValueError):
		return HttpResponse("That user does not exist.", status=404)

	if account != user:
		return HttpResponse("You can't view another users friend requests.", status=403)

	return render(request, "friend/friend_requests.html", {
		'friend_requests': FriendRequest.objects.filter(receiver=account, is_active=True),
	})


@login_required(login_url='login')
@require_POST
def accept_friend_request(request, *args, **kwargs):
	"""Accepte une demande d'ami.

	POST obligatoire : la vue répondait auparavant au GET, si bien qu'un
	simple <img src="/friend/friend_request_accept/12/"> sur un site tiers
	faisait accepter la demande à l'insu de l'utilisateur (le middleware CSRF
	ne contrôle pas les requêtes GET).
	"""
	friend_request_id = kwargs.get("friend_request_id")
	try:
		friend_request = FriendRequest.objects.get(pk=friend_request_id)
	except (FriendRequest.DoesNotExist, ValueError):
		return _json({'response': "Unable to accept that friend request."}, status=404)

	if friend_request.receiver != request.user:
		return _json({'response': "That is not your request to accept."}, status=403)

	friend_request.accept()
	return _json({'response': "Friend request accepted."})


@login_required(login_url='login')
@require_POST
def remove_friend(request, *args, **kwargs):
	user_id = request.POST.get("receiver_user_id")
	if not user_id:
		return _json({'response': "There was an error. Unable to remove that friend."}, status=400)

	try:
		removee = Account.objects.get(pk=user_id)
	except (Account.DoesNotExist, ValueError):
		return _json({'response': "That user does not exist."}, status=404)

	friend_list, _ = FriendList.objects.get_or_create(user=request.user)
	friend_list.unfriend(removee)
	return _json({'response': "Successfully removed that friend."})


@login_required(login_url='login')
@require_POST
def decline_friend_request(request, *args, **kwargs):
	"""Refuse une demande d'ami. POST obligatoire (voir accept_friend_request)."""
	friend_request_id = kwargs.get("friend_request_id")
	try:
		friend_request = FriendRequest.objects.get(pk=friend_request_id)
	except (FriendRequest.DoesNotExist, ValueError):
		return _json({'response': "Unable to decline that friend request."}, status=404)

	if friend_request.receiver != request.user:
		return _json({'response': "That is not your friend request to decline."}, status=403)

	friend_request.decline()
	return _json({'response': "Friend request declined."})


@login_required(login_url='login')
@require_POST
def cancel_friend_request(request, *args, **kwargs):
	user_id = request.POST.get("receiver_user_id")
	if not user_id:
		return _json({'response': "Unable to cancel that friend request."}, status=400)

	try:
		receiver = Account.objects.get(pk=user_id)
	except (Account.DoesNotExist, ValueError):
		return _json({'response': "That user does not exist."}, status=404)

	friend_requests_qs = FriendRequest.objects.filter(
		sender=request.user, receiver=receiver, is_active=True
	)
	# `.first().cancel()` levait une AttributeError (None) quand il n'y avait
	# aucune demande active — erreur 500 au lieu d'un message clair.
	if not friend_requests_qs.exists():
		return _json({'response': "Nothing to cancel. Friend request does not exist."}, status=404)

	# Il ne devrait y avoir qu'une seule demande active ; on les annule toutes.
	for friend_req in friend_requests_qs:
		friend_req.cancel()
	return _json({'response': "Friend request canceled."})


@login_required(login_url='login')
def friends_list_view(request, *args, **kwargs):
	user = request.user
	user_id = kwargs.get("user_id")

	try:
		this_user = Account.objects.get(pk=user_id)
	except (Account.DoesNotExist, ValueError):
		return HttpResponse("That user does not exist.", status=404)

	friend_list, _ = FriendList.objects.get_or_create(user=this_user)

	# Must be friends to view a friends list
	if user != this_user and user not in friend_list.friends.all():
		return HttpResponse("You must be friends to view their friends list.", status=403)

	auth_user_friend_list, _ = FriendList.objects.get_or_create(user=user)
	friends = [
		(friend, auth_user_friend_list.is_mutual_friend(friend))
		for friend in friend_list.friends.all()
	]

	return render(request, "friend/friend_list.html", {
		'this_user': this_user,
		'friends':   friends,
	})
