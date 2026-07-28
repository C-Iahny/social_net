from django import forms
from .models import Post, Comment

ACCEPTED_IMAGES = (
    'image/jpeg,image/jpg,image/png,image/gif,image/webp,'
    'image/bmp,image/tiff,image/heic,image/heif,'
    '.jpg,.jpeg,.png,.gif,.webp,.bmp,.tiff,.tif,.heic,.heif'
)

ACCEPTED_VIDEOS = (
    'video/mp4,video/webm,video/ogg,video/quicktime,'
    'video/x-msvideo,video/x-matroska,'
    '.mp4,.webm,.ogg,.mov,.mkv,.avi,.m4v,.3gp'
)


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ('title', 'body', 'header_image', 'video', 'file')
        widgets = {
            'title':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'title required'}),
            'body':         forms.Textarea(attrs={'class': 'form-control'}),
            'header_image': forms.FileInput(attrs={'class': 'form-control', 'accept': ACCEPTED_IMAGES}),
            'video':        forms.FileInput(attrs={'class': 'form-control', 'accept': ACCEPTED_VIDEOS}),
            'file':         forms.FileInput(attrs={'class': 'form-control'}),
        }


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ('body',)
        widgets = {
            'body': forms.Textarea(attrs={
                'class':       'form-control',
                'placeholder': 'Écrire un commentaire…',
                'rows':        2,
                'maxlength':   1000,
            }),
        }


class EditForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ('title', 'body', 'header_image', 'video', 'file')
        widgets = {
            'title':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'title required'}),
            'body':         forms.Textarea(attrs={'class': 'form-control'}),
            'header_image': forms.FileInput(attrs={'class': 'form-control', 'accept': ACCEPTED_IMAGES}),
            'video':        forms.FileInput(attrs={'class': 'form-control', 'accept': ACCEPTED_VIDEOS}),
            'file':         forms.FileInput(attrs={'class': 'form-control'}),
        }
