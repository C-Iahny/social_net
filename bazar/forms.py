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
            'listing_type',
            'title', 'category', 'condition',
            'price', 'price_negotiable',
            # Location-specific
            'prix_location', 'periode_location',
            'caution', 'duree_min',
            # Appartement
            'nb_pieces', 'surface_m2', 'meuble', 'charges_incluses',
            # Voiture en location
            'avec_chauffeur',
            'description',
            'location', 'region',
            'contact_phone', 'show_phone',
            'status',
        ]
        widgets = {
            'listing_type': forms.RadioSelect(attrs={'class': 'form-check-input'}),
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
            # Location-specific widgets
            'prix_location': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 150000',
                'min': 0,
            }),
            'periode_location': forms.Select(attrs={'class': 'form-control'}),
            'caution': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 300000',
                'min': 0,
            }),
            'duree_min': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 7',
                'min': 1,
            }),
            # Appartement
            'nb_pieces': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 3',
                'min': 1,
            }),
            'surface_m2': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 65',
                'min': 1,
                'step': '0.1',
            }),
            'meuble': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'charges_incluses': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            # Voiture
            'avec_chauffeur': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
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
                    ('louee',  'Louée — archivée'),
                ],
            ),
        }
        labels = {
            'listing_type':      'Type d\'annonce',
            'title':             'Titre de l\'annonce',
            'category':          'Catégorie',
            'condition':         'État',
            'price':             'Prix (Ariary)',
            'price_negotiable':  'Prix négociable',
            'prix_location':     'Prix de location (Ariary)',
            'periode_location':  'Période',
            'caution':           'Caution (Ariary)',
            'duree_min':         'Durée minimale (jours)',
            'nb_pieces':         'Nombre de pièces',
            'surface_m2':        'Surface (m²)',
            'meuble':            'Meublé',
            'charges_incluses':  'Charges incluses',
            'avec_chauffeur':    'Avec chauffeur',
            'description':       'Description',
            'location':          'Ville / quartier',
            'region':            'Région',
            'contact_phone':     'Téléphone / WhatsApp',
            'show_phone':        'Afficher le numéro publiquement',
            'status':            'Statut de l\'annonce',
        }

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is not None and price < 0:
            raise ValidationError('Le prix ne peut pas être négatif.')
        return price

    def clean_prix_location(self):
        prix = self.cleaned_data.get('prix_location')
        if prix is not None and prix < 0:
            raise ValidationError('Le prix de location ne peut pas être négatif.')
        return prix

    def clean_caution(self):
        caution = self.cleaned_data.get('caution')
        if caution is not None and caution < 0:
            raise ValidationError('La caution ne peut pas être négative.')
        return caution
