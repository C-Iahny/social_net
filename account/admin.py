from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from account.models import Account, PhoneVerification
from django.contrib.auth.models import User



class AccountAdmin(UserAdmin):
	list_display = (
		'email', 'username', 'date_joined', 'last_login',
		'is_admin', 'is_staff', 'cgu_accepted_at',
		'phone_number', 'phone_verified',
	)
	search_fields = ('email', 'username', 'phone_number',)
	readonly_fields = ('id', 'date_joined', 'last_login', 'cgu_accepted_at')

	filter_horizontal = ()
	list_filter = ('is_admin', 'is_staff', 'phone_verified')
	fieldsets = (
		('Compte', {'fields': ('id', 'email', 'username', 'password')}),
		('Profil', {'fields': ('profile_image', 'cover_image', 'bio', 'location', 'region')}),
		('Téléphone', {'fields': ('phone_number', 'phone_verified')}),
		('Permissions', {'fields': ('is_active', 'is_admin', 'is_staff', 'is_superuser')}),
		('Dates', {'fields': ('date_joined', 'last_login')}),
		('CGU & Confidentialité', {'fields': ('cgu_accepted_at',)}),
	)


admin.site.register(Account, AccountAdmin)


@admin.register(PhoneVerification)
class PhoneVerificationAdmin(admin.ModelAdmin):
	list_display  = ('user', 'phone', 'verified', 'attempts', 'created_at')
	list_filter   = ('verified',)
	search_fields = ('user__username', 'user__email', 'phone')
	readonly_fields = ('user', 'phone', 'code', 'created_at', 'attempts', 'verified')
	ordering = ('-created_at',)



