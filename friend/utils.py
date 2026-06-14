from friend.models import FriendRequest


def get_friend_request_or_false(sender, receiver):
	"""
	Retourne la demande d'ami ACTIVE de sender vers receiver, ou False.
	Utilise .filter().first() pour éviter MultipleObjectsReturned si des
	doublons existent en base (cas de bug historique).
	"""
	fr = FriendRequest.objects.filter(
		sender=sender,
		receiver=receiver,
		is_active=True,
	).first()
	return fr if fr is not None else False