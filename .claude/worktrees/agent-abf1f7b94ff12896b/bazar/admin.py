from datetime import timedelta

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from .models import Annonce, AnnonceImage, SellerVerification


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


# ── SellerVerification ──────────────────────────────────────────────────────────

def _action_approve(modeladmin, request, queryset):
    """Action admin : approuver les demandes sélectionnées."""
    updated = 0
    for verif in queryset.exclude(status=SellerVerification.STATUS_APPROVED):
        verif.approve(reviewed_by=request.user)
        updated += 1
    modeladmin.message_user(request, f'{updated} vendeur(s) approuvé(s).')

_action_approve.short_description = '✅ Approuver les demandes sélectionnées'


def _action_reject(modeladmin, request, queryset):
    """Action admin : rejeter les demandes sélectionnées."""
    updated = 0
    for verif in queryset.exclude(status=SellerVerification.STATUS_REJECTED):
        verif.reject(reviewed_by=request.user)
        updated += 1
    modeladmin.message_user(request, f'{updated} vendeur(s) refusé(s).')

_action_reject.short_description = '❌ Refuser les demandes sélectionnées'


def _action_reset(modeladmin, request, queryset):
    """Action admin : remettre en attente."""
    queryset.update(
        status=SellerVerification.STATUS_PENDING,
        reviewed_at=None,
        reviewed_by=None,
    )
    modeladmin.message_user(request, f'{queryset.count()} demande(s) remise(s) en attente.')

_action_reset.short_description = '🔄 Remettre en attente'


@admin.register(SellerVerification)
class SellerVerificationAdmin(admin.ModelAdmin):
    list_display  = (
        'seller', '_type_badge', '_status_badge',
        'boutique_name', 'created_at', 'reviewed_at', 'reviewed_by',
    )
    list_filter   = ('status', 'seller_type')
    search_fields = (
        'seller__username', 'seller__email',
        'message', 'admin_notes',
        'boutique_name', 'boutique_address',
    )
    readonly_fields = (
        'seller', 'message', 'created_at', 'reviewed_at', 'reviewed_by',
        '_status_badge', '_type_badge', '_banner_preview',
    )
    ordering      = ['-created_at']
    actions       = [_action_approve, _action_reject, _action_reset]

    fieldsets = (
        ('Vendeur', {
            'fields': ('seller', 'seller_type', '_type_badge', '_status_badge', 'status'),
        }),
        ('Demande du vendeur', {
            'fields': ('message', 'created_at'),
        }),
        ('Boutique (Concessionnaire / Pro)', {
            'classes': ('collapse',),
            'fields': (
                'boutique_name', 'boutique_category',
                'boutique_description',
                'boutique_phone', 'boutique_address', 'boutique_hours',
                '_banner_preview', 'boutique_banner',
            ),
        }),
        ('Décision admin', {
            'fields': ('admin_notes', 'reviewed_at', 'reviewed_by'),
        }),
        ('Abonnement', {
            'classes': ('collapse',),
            'fields': ('approved_at', 'free_until'),
        }),
    )

    def _type_badge(self, obj):
        if obj.seller_type == SellerVerification.SELLER_TYPE_PRO:
            return format_html(
                '<span style="color:#d97706;font-weight:700;">⭐ Boutique Pro</span>'
            )
        return format_html(
            '<span style="color:#6b7280;font-weight:600;">👤 Vendeur Vérifié</span>'
        )
    _type_badge.short_description = 'Type'

    def _status_badge(self, obj):
        colors = {
            SellerVerification.STATUS_PENDING:  ('#f59e0b', '⏳ En attente'),
            SellerVerification.STATUS_APPROVED: ('#10b981', '✅ Approuvé'),
            SellerVerification.STATUS_REJECTED: ('#ef4444', '❌ Refusé'),
        }
        color, label = colors.get(obj.status, ('#6b7280', obj.get_status_display()))
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>',
            color, label,
        )
    _status_badge.short_description = 'Statut'

    def _banner_preview(self, obj):
        if obj.boutique_banner:
            return format_html(
                '<img src="{}" style="max-width:320px;max-height:80px;border-radius:8px;object-fit:cover;">',
                obj.boutique_banner.url,
            )
        return '— pas de bannière —'
    _banner_preview.short_description = 'Aperçu bannière'

    def save_model(self, request, obj, form, change):
        """Met à jour reviewed_at / reviewed_by + approved_at quand le statut change."""
        if change and 'status' in form.changed_data:
            if obj.status in (SellerVerification.STATUS_APPROVED, SellerVerification.STATUS_REJECTED):
                obj.reviewed_at = timezone.now()
                obj.reviewed_by = request.user
            if obj.status == SellerVerification.STATUS_APPROVED and not obj.approved_at:
                obj.approved_at = timezone.now()
                obj.free_until  = obj.approved_at + timedelta(days=365)
        super().save_model(request, obj, form, change)
