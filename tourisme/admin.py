from django.contrib import admin
from .models import LieuTouristique, LieuImage, GuideTouristique


class LieuImageInline(admin.TabularInline):
    model = LieuImage
    extra = 3
    fields = ('image', 'caption', 'is_primary', 'order')


@admin.register(LieuTouristique)
class LieuTouristiqueAdmin(admin.ModelAdmin):
    list_display  = ('name', 'category', 'region', 'is_approved', 'views_count', 'created_at')
    list_filter   = ('is_approved', 'category', 'region')
    list_editable = ('is_approved',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [LieuImageInline]
    actions = ['approve_lieux', 'unapprove_lieux']

    def approve_lieux(self, request, qs):
        qs.update(is_approved=True)
        self.message_user(request, f'{qs.count()} lieu(x) approuvé(s).')
    approve_lieux.short_description = 'Approuver'

    def unapprove_lieux(self, request, qs):
        qs.update(is_approved=False)
    unapprove_lieux.short_description = 'Désapprouver'


@admin.register(GuideTouristique)
class GuideTouristiqueAdmin(admin.ModelAdmin):
    list_display  = ('display_name_col', 'is_verified', 'is_active', 'prix_jour', 'years_experience', 'created_at')
    list_filter   = ('is_verified', 'is_active')
    list_editable = ('is_verified', 'is_active')
    search_fields = ('user__username', 'user__first_name', 'bio', 'specialities')
    raw_id_fields = ('user',)

    def display_name_col(self, obj):
        return str(obj)
    display_name_col.short_description = 'Guide'
