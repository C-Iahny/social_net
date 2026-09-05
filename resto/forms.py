from django import forms
from django.utils.translation import gettext_lazy as _

from regions import REGION_CHOICES
from .models import Restaurant, MenuItem, MenuCategory, Courier, Order


_INPUT = {'class': 'form-control'}
_CHECK = {'class': 'form-check-input'}


class RestaurantForm(forms.ModelForm):
    class Meta:
        model = Restaurant
        fields = [
            'name', 'category', 'description', 'logo', 'banner',
            'phone', 'address', 'region', 'latitude', 'longitude',
            'opening_hours', 'offers_delivery', 'offers_pickup',
            'delivery_fee', 'min_order', 'avg_prep_minutes',
        ]
        widgets = {
            'name':        forms.TextInput(attrs={**_INPUT, 'placeholder': _('Ex : Hotely Mamy, Pizza Tana…')}),
            'category':    forms.Select(attrs=_INPUT),
            'description': forms.Textarea(attrs={**_INPUT, 'rows': 3, 'placeholder': _('Spécialités, ambiance, ce qui vous distingue')}),
            'logo':        forms.ClearableFileInput(attrs={'accept': 'image/*,.heic,.heif'}),
            'banner':      forms.ClearableFileInput(attrs={'accept': 'image/*,.heic,.heif'}),
            'phone':       forms.TextInput(attrs={**_INPUT, 'placeholder': '+261 34 XX XXX XX'}),
            'address':     forms.TextInput(attrs={**_INPUT, 'placeholder': _('Quartier, rue, repère')}),
            'region':      forms.Select(attrs=_INPUT, choices=REGION_CHOICES),
            'latitude':    forms.HiddenInput(),
            'longitude':   forms.HiddenInput(),
            'opening_hours':   forms.TextInput(attrs={**_INPUT, 'placeholder': _('Ex : Lun–Sam 10h–22h')}),
            'offers_delivery': forms.CheckboxInput(attrs=_CHECK),
            'offers_pickup':   forms.CheckboxInput(attrs=_CHECK),
            'delivery_fee':    forms.NumberInput(attrs={**_INPUT, 'min': 0, 'step': 100}),
            'min_order':       forms.NumberInput(attrs={**_INPUT, 'min': 0, 'step': 500}),
            'avg_prep_minutes': forms.NumberInput(attrs={**_INPUT, 'min': 5, 'max': 180}),
        }

    def clean(self):
        data = super().clean()
        if not data.get('offers_delivery') and not data.get('offers_pickup'):
            raise forms.ValidationError(_('Activez au moins la livraison ou le retrait sur place.'))
        for f in ('delivery_fee', 'min_order'):
            if data.get(f) is not None and data[f] < 0:
                self.add_error(f, _('Le montant ne peut pas être négatif.'))
        return data


class MenuCategoryForm(forms.ModelForm):
    class Meta:
        model = MenuCategory
        fields = ['name', 'order']
        widgets = {
            'name':  forms.TextInput(attrs={**_INPUT, 'placeholder': _('Ex : Plats, Boissons, Desserts')}),
            'order': forms.NumberInput(attrs={**_INPUT, 'min': 0}),
        }


class MenuItemForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = ['category', 'name', 'description', 'ingredients', 'preparation', 'price', 'image', 'is_available', 'order']
        widgets = {
            'category':    forms.Select(attrs=_INPUT),
            'name':        forms.TextInput(attrs={**_INPUT, 'placeholder': _('Ex : Ravitoto sy henakisoa')}),
            'description': forms.Textarea(attrs={**_INPUT, 'rows': 2, 'placeholder': _('Portion, accompagnement, particularités')}),
            'ingredients': forms.Textarea(attrs={**_INPUT, 'rows': 4, 'placeholder': _('Un ingrédient par ligne : Oignons, Piment, !Riz (obligatoire)')}),
            'preparation': forms.Textarea(attrs={**_INPUT, 'rows': 3, 'placeholder': _('Ex : Porc mijoté 2 h avec les feuilles de manioc pilées, servi avec du riz blanc')}),
            'price':       forms.NumberInput(attrs={**_INPUT, 'min': 0, 'step': 100}),
            'image':       forms.ClearableFileInput(attrs={'accept': 'image/*,.heic,.heif'}),
            'is_available': forms.CheckboxInput(attrs=_CHECK),
            'order':       forms.NumberInput(attrs={**_INPUT, 'min': 0}),
        }

    def __init__(self, *args, restaurant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if restaurant is not None:
            self.fields['category'].queryset = restaurant.menu_categories.all()
        self.fields['category'].required = False

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is not None and price < 0:
            raise forms.ValidationError(_('Le prix ne peut pas être négatif.'))
        return price


class CheckoutForm(forms.ModelForm):
    """Étape « Commander » : coordonnées, mode de réception, paiement."""
    class Meta:
        model = Order
        fields = ['mode', 'customer_name', 'customer_phone', 'delivery_address',
                  'delivery_latitude', 'delivery_longitude', 'payment_method', 'note']
        widgets = {
            'mode':             forms.RadioSelect(),
            'customer_name':    forms.TextInput(attrs={**_INPUT, 'placeholder': _('Votre nom')}),
            'customer_phone':   forms.TextInput(attrs={**_INPUT, 'placeholder': '+261 34 XX XXX XX'}),
            'delivery_address': forms.TextInput(attrs={**_INPUT, 'placeholder': _('Quartier, rue, porte, repère pour le livreur')}),
            'delivery_latitude':  forms.HiddenInput(),
            'delivery_longitude': forms.HiddenInput(),
            'payment_method':   forms.RadioSelect(),
            'note':             forms.Textarea(attrs={**_INPUT, 'rows': 2, 'placeholder': _('Message au restaurant (facultatif)')}),
        }

    def __init__(self, *args, restaurant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.restaurant = restaurant
        modes = []
        if restaurant is None or restaurant.offers_delivery:
            modes.append((Order.MODE_DELIVERY, _('Livraison')))
        if restaurant is None or restaurant.offers_pickup:
            modes.append((Order.MODE_PICKUP, _('Retrait sur place')))
        self.fields['mode'].choices = modes
        if modes:
            self.fields['mode'].initial = modes[0][0]

    def clean(self):
        data = super().clean()
        if data.get('mode') == Order.MODE_DELIVERY and not (data.get('delivery_address') or '').strip():
            self.add_error('delivery_address', _('Indiquez où livrer.'))
        return data


class CourierForm(forms.ModelForm):
    """Profil livreur complet : identité, véhicule, zone, paiement, garant."""
    class Meta:
        model = Courier
        fields = ['full_name', 'photo', 'phone', 'bio',
                  'cin_number', 'cin_front', 'cin_back',
                  'vehicle', 'vehicle_plate', 'vehicle_photo',
                  'region', 'zones', 'hours', 'languages', 'years_experience',
                  'mm_provider', 'mm_number',
                  'guarantor_name', 'guarantor_phone']
        widgets = {
            'full_name':     forms.TextInput(attrs={**_INPUT, 'placeholder': _('Ex : RAKOTO Jean Mamy')}),
            'photo':         forms.ClearableFileInput(attrs={'accept': 'image/*,.heic,.heif', 'capture': 'user'}),
            'phone':         forms.TextInput(attrs={**_INPUT, 'placeholder': '+261 34 XX XXX XX'}),
            'bio':           forms.Textarea(attrs={**_INPUT, 'rows': 2}),
            'cin_number':    forms.TextInput(attrs={**_INPUT, 'placeholder': '101 011 234 567', 'inputmode': 'numeric'}),
            'cin_front':     forms.ClearableFileInput(attrs={'accept': 'image/*,.heic,.heif', 'capture': 'environment'}),
            'cin_back':      forms.ClearableFileInput(attrs={'accept': 'image/*,.heic,.heif', 'capture': 'environment'}),
            'vehicle':       forms.Select(attrs=_INPUT),
            'vehicle_plate': forms.TextInput(attrs={**_INPUT, 'placeholder': _('Ex : 1234 TAB')}),
            'vehicle_photo': forms.ClearableFileInput(attrs={'accept': 'image/*,.heic,.heif'}),
            'region':        forms.Select(attrs=_INPUT, choices=REGION_CHOICES),
            'zones':         forms.TextInput(attrs=_INPUT),
            'hours':         forms.TextInput(attrs=_INPUT),
            'languages':     forms.TextInput(attrs=_INPUT),
            'years_experience': forms.NumberInput(attrs={**_INPUT, 'min': 0, 'max': 50}),
            'mm_provider':   forms.Select(attrs=_INPUT),
            'mm_number':     forms.TextInput(attrs={**_INPUT, 'placeholder': '034 XX XXX XX'}),
            'guarantor_name':  forms.TextInput(attrs=_INPUT),
            'guarantor_phone': forms.TextInput(attrs={**_INPUT, 'placeholder': '+261 3X XX XXX XX'}),
        }

    def clean_cin_number(self):
        raw = (self.cleaned_data.get('cin_number') or '').replace(' ', '')
        if raw and (not raw.isdigit() or len(raw) != 12):
            raise forms.ValidationError(_('La CIN malgache comporte 12 chiffres.'))
        return raw

    def clean(self):
        data = super().clean()
        if data.get('mm_provider') and not (data.get('mm_number') or '').strip():
            self.add_error('mm_number', _('Indiquez le numéro mobile money.'))
        if data.get('vehicle') != 'pied' and not data.get('vehicle_plate') and data.get('vehicle') != 'velo':
            self.add_error('vehicle_plate', _('Indiquez l\'immatriculation du véhicule.'))
        return data
