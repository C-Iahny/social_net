from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate

from .models import Account


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(max_length=254, help_text='Required. Add a valid email address.')

    class Meta:
        model = Account
        fields = ('email', 'username', 'password1', 'password2', )

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        try:
            account = Account.objects.exclude(pk=self.instance.pk).get(email=email)
        except Account.DoesNotExist:
            return email
        raise forms.ValidationError('Email "%s" is already in use.' % account.email)

    def clean_username(self):
        username = self.cleaned_data['username']
        try:
            account = Account.objects.exclude(pk=self.instance.pk).get(username=username)
        except Account.DoesNotExist:
            return username
        raise forms.ValidationError('Username "%s" is already in use.' % username)



class AccountAuthenticationForm(forms.ModelForm):

    password = forms.CharField(label='Password', widget=forms.PasswordInput)

    class Meta:
        model = Account
        fields = ('email', 'password')

    def clean(self):
        if self.is_valid():
            email = self.cleaned_data['email']
            password = self.cleaned_data['password']
            if not authenticate(email=email, password=password):
                raise forms.ValidationError("Invalid login")


ACCEPTED_IMAGE_TYPES = (
    'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
    'image/webp', 'image/bmp', 'image/tiff', 'image/heic', 'image/heif',
)
ACCEPTED_IMAGE_EXTENSIONS = '.jpg,.jpeg,.png,.gif,.webp,.bmp,.tiff,.tif,.heic,.heif'


class AccountUpdateForm(forms.ModelForm):

    bio = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Parlez un peu de vous...'}),
        label='Bio',
    )
    location = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'Ville, Pays'}),
        label='Localisation',
    )
    region = forms.ChoiceField(
        required=False,
        label='Région',
        choices=[],  # rempli dynamiquement dans __init__
        widget=forms.Select(),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from regions import REGION_CHOICES
        self.fields['region'].choices = REGION_CHOICES

    class Meta:
        model = Account
        fields = ('username', 'email', 'profile_image', 'hide_email', 'bio', 'location', 'region')
        widgets = {
            'profile_image': forms.FileInput(attrs={
                'accept': ACCEPTED_IMAGE_EXTENSIONS,
            }),
        }

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        try:
            account = Account.objects.exclude(pk=self.instance.pk).get(email=email)
        except Account.DoesNotExist:
            return email
        raise forms.ValidationError('Email "%s" is already in use.' % account.email)

    def clean_username(self):
        username = self.cleaned_data['username']
        try:
            account = Account.objects.exclude(pk=self.instance.pk).get(username=username)
        except Account.DoesNotExist:
            return username
        raise forms.ValidationError('Username "%s" is already in use.' % username)

    def save(self, commit=True):
        account = super(AccountUpdateForm, self).save(commit=False)
        account.username   = self.cleaned_data['username']
        account.email      = self.cleaned_data['email'].lower()
        account.hide_email = self.cleaned_data['hide_email']
        account.bio        = self.cleaned_data.get('bio', '')
        account.location   = self.cleaned_data.get('location', '')
        account.region     = self.cleaned_data.get('region', '')
        # Ne remplace la photo que si un nouveau fichier est uploadé
        new_image = self.cleaned_data.get('profile_image')
        if new_image:
            account.profile_image = new_image
        if commit:
            account.save()
        return account
