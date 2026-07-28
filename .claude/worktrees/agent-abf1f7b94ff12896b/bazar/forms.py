from django import forms
from django.core.exceptions import ValidationError
from .models import Annonce, AnnonceImage

try:
    from regions import REGION_CHOICES
except ImportError:
    REGION_CHOICES = []


class AnnonceForm(forms.ModelForm):
    """
    Formulaire principal de création / modification d'annonce.
    Les photos sont gérées séparément via request.FILES.getlist('images') dans la vue.
    """

    class Meta:
        model = Annonce
        fields = [
            'title', 'category', 'condition',
            'price', 'price_negotiable',
            'description',
            'location', 'region',
            'contact_phone', 'show_phone',
            'status',
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
            'region': forms.Select(
                attrs={'class': 'form-control'},
                choices=[('', 'Toute Madagascar')] + list(REGION_CHOICES),
            ),
            'contact_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: +261 34 00 000 00',
            }),
            'show_phone': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'status': forms.Select(
                attrs={'class': 'form-control'},
                # Exclure 'expiree' (géré automatiquement par le système)
                choices=[
                    ('active', 'Active — visible par tous'),
                    ('pause',  'En pause — masquée temporairement'),
                    ('vendue', 'Vendue — archivée'),
                ],
            ),
        }
        labels = {
            'title':            'Titre de l\'annonce',
            'category':         'Catégorie',
            'condition':        'État',
            'price':            'Prix (Ariary)',
            'price_negotiable': 'Prix négociable',
            'description':      'Description',
            'location':         'Ville / quartier',
            'region':           'Région',
            'contact_phone':    'Téléphone / WhatsApp',
            'show_phone':       'Afficher le numéro publiquement',
            'status':           'Statut de l\'annonce',
        }

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is not None and price < 0:
            raise ValidationError('Le prix ne peut pas être négatif.')
        return price
