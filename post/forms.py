from django import forms 
from .models import Post




class PostForm(forms.ModelForm):
	class Meta:
		model = Post 
		fields = (
			#'title',
			# 'author', 
			#'category', 
			'body', 
			#'snippet', 
			'header_image', 
			'file',

		)

		widgets = {

			#'title': forms.TextInput(attrs={'class': 'form-control'}),
			#'author': forms.Select(attrs={'class': 'form-control'}),
			#'author': forms.TextInput(attrs={'class': 'form-control', 'value': '', 'id': 'Ihany', 'type': 'hidden'}),
			#'category': forms.Select(choices=choice_list, attrs={'class': 'form-control'}),
			'body': forms.Textarea(attrs={'class': 'form-control'}),
			#'snippet': forms.Textarea(attrs={'class': 'form-control'}),
			'header_image': forms.FileInput(attrs={'class': 'form-control'}),
			'file': forms.FileInput(attrs={'class': 'form-control'}),

		}