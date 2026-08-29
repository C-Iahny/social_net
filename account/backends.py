from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class CaseInsensitiveModelBackend(ModelBackend):
    """
    Authentification par e-mail insensible à la casse.

    Hérite de ModelBackend : user_can_authenticate() rejette les comptes
    désactivés (is_active=False). C'est le seul backend du projet — voir
    le commentaire dans settings.AUTHENTICATION_BACKENDS.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None
        try:
            case_insensitive_username_field = '{}__iexact'.format(UserModel.USERNAME_FIELD)
            user = UserModel._default_manager.get(**{case_insensitive_username_field: username})
        except UserModel.DoesNotExist:
            # Run the default password hasher once to reduce the timing
            # difference between an existing and a non-existing user (#20760).
            UserModel().set_password(password)
        except UserModel.MultipleObjectsReturned:
            # Deux comptes ne différant que par la casse de l'e-mail (créés en
            # ligne de commande, la validation du formulaire minusculise).
            # On ne devine pas lequel : on refuse plutôt que de lever une 500.
            UserModel().set_password(password)
        else:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None
