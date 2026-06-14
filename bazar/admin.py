from django.contrib import admin
from django.utils.html import format_html
from .models import Annonce, AnnonceImage


class AnnonceImageInline(admin.TabularInline):
    model   = AnnonceImage
    extra   = 0
    fields  = ('image', 'is_primary', 'order', '_preview')
    readonly_fields = ('_preview',)

    def _preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:60px;border-radius:4px;">', obj.image.url)
        return '—'
    _preview.short_description = 'Aperçu'


@admin.register(Annonce)
class AnnonceAdmin(admin.ModelAdmin):
    list_display  = ('title', 'seller', 'category', 'formatted_price_admin', 'status', 'views_count', 'created_at')
    list_filter   = ('status', 'category', 'condition')
    search_fields = ('title', 'description', 'seller__username', 'location')
    readonly_fields = ('views_count', 'created_at', 'updated_at')
    list_editable = ('status',)
    ordering      = ('-created_at',)
    date_hierarchy = 'created_at'
    inlines       = [AnnonceImageInline]

    fieldsets = (
        ('Annonce', {
            'fields': ('seller', 'title', 'category', 'condition', 'description'),
        }),
        ('Prix & Contact', {
            'fields': ('price', 'price_negotiable', 'contact_phone', 'show_phone', 'location'),
        }),
        ('Statut & Stats', {
            'fields': ('status', 'views_count', 'created_at', 'updated_at'),
        }),
    )

    def formatted_price_admin(self, obj):
        return obj.formatted_price
    formatted_price_admin.short_description = 'Prix'


@admin.register(AnnonceImage)
class AnnonceImageAdmin(admin.ModelAdmin):
    list_display  = ('annonce', 'is_primary', 'order', '_preview')
    list_filter   = ('is_primary',)
    readonly_fields = ('_preview',)

    def _preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:60px;border-radius:4px;">', obj.image.url)
        return '—'
    _preview.short_description = 'Aperçu'
