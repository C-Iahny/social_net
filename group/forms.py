from django import forms

from .models import Group


class GroupForm(forms.ModelForm):
    """Formulaire de création / édition d'un groupe."""

    class Meta:
        model = Group
        fields = ['name', 'description', 'cover', 'privacy']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'gp-input',
                'placeholder': 'Nom du groupe',
                'maxlength': 100,
                'autofocus': True,
            }),
            'description': forms.Textarea(attrs={
                'class': 'gp-input',
                'rows': 4,
                'placeholder': 'Décrivez votre groupe…',
                'maxlength': 500,
            }),
            'privacy': forms.Select(attrs={'class': 'gp-input'}),
        }
        labels = {
            'name': 'Nom',
            'description': 'Description',
            'cover': 'Image de couverture',
            'privacy': 'Confidentialité',
        }

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if len(name) < 3:
            raise forms.ValidationError("Le nom doit contenir au moins 3 caractères.")
        return name
