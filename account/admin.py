from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from account.models import Account
from django.contrib.auth.models import User



class AccountAdmin(UserAdmin):
	list_display = (
		'email', 'username', 'date_joined', 'last_login',
		'is_admin', 'is_staff', 'cgu_accepted_at',
	)
	search_fields = ('email', 'username',)
	readonly_fields = ('id', 'date_joined', 'last_login', 'cgu_accepted_at')

	filter_horizontal = ()
	list_filter = ('is_admin', 'is_staff')
	fieldsets = (
		('Compte', {'fields': ('id', 'email', 'username', 'password')}),
		('Profil', {'fields': ('profile_image', 'cover_image', 'bio', 'location')}),
		('Permissions', {'fields': ('is_active', 'is_admin', 'is_staff', 'is_superuser')}),
		('Dates', {'fields': ('date_joined', 'last_login')}),
		('CGU & Confidentialité', {'fields': ('cgu_accepted_at',)}),
	)


admin.site.register(Account, AccountAdmin)



