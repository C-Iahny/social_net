from django import forms
from django.core.exceptions import ValidationError
from .models import Annonce, AnnonceImage


class AnnonceForm(forms.ModelForm):
    """Formulaire principal de création / modification d'annonce."""

    # Champ images multiple — géré manuellement dans la vue
    images = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'multiple': True,
            'accept': 'image/*',
            'id': 'id_images',
            'class': 'bazar-file-input',
        }),
        label='Photos',
        help_text='Jusqu\'à 8 photos. La première sera la photo principale.',
    )

    class Meta:
        model = Annonce
        fields = [
            'title', 'category', 'condition',
            'price', 'price_negotiable',
            'description', 'location',
            'contact_phone', 'show_phone',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Samsung Galaxy A54 128Go',
                'maxlength': 180,
            }),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'condition': forms.Select(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 250000',
                'min': 0,
            }),
            'price_negotiable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Décrivez votre article : marque, modèle, défauts éventuels…',
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Antananarivo, Analakely',
            }),
            'contact_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: +261 34 00 000 00',
            }),
            'show_phone': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'title':            'Titre de l\'annonce',
            'category':         'Catégorie',
            'condition':        'État',
            'price':            'Prix (Ariary)',
            'price_negotiable': 'Prix négociable',
            'description':      'Description',
            'location':         'Localisation',
            'contact_phone':    'Téléphone / WhatsApp',
            'show_phone':       'Afficher le numéro publiquement',
        }

    def clean_images(self):
        # On récupère les fichiers depuis request.FILES dans la vue
        return self.cleaned_data.get('images')

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is not None and price < 0:
            raise ValidationError('Le prix ne peut pas être négatif.')
        return price
