from django.contrib import admin

from .models import (
    Restaurant, MenuCategory, MenuItem, OptionGroup, Option,
    Courier, Cart, CartItem, Order, OrderItem, OrderItemOption, OrderEvent, OrderReview,
)


class MenuCategoryInline(admin.TabularInline):
    model = MenuCategory
    extra = 0


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display  = ('name', 'owner', 'category', 'region', 'is_approved', 'is_active', 'is_open', 'created_at')
    list_filter   = ('is_approved', 'is_active', 'is_open', 'category', 'region')
    search_fields = ('name', 'owner__username', 'address', 'phone')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [MenuCategoryInline]
    actions = ['approve']

    @admin.action(description='Approuver les restaurants sélectionnés')
    def approve(self, request, queryset):
        queryset.update(is_approved=True)


class OptionInline(admin.TabularInline):
    model = Option
    extra = 0


@admin.register(OptionGroup)
class OptionGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'item', 'min_select', 'max_select')
    inlines = [OptionInline]


class OptionGroupInline(admin.TabularInline):
    model = OptionGroup
    extra = 0
    show_change_link = True


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display  = ('name', 'restaurant', 'category', 'price', 'is_available')
    list_filter   = ('is_available', 'restaurant')
    search_fields = ('name', 'restaurant__name')
    inlines = [OptionGroupInline]


@admin.register(Courier)
class CourierAdmin(admin.ModelAdmin):
    list_display  = ('display_name', 'user', 'restaurant', 'vehicle', 'vehicle_plate', 'region',
                     'is_approved', 'cin_verified', 'is_available', 'position_updated_at')
    list_filter   = ('is_approved', 'cin_verified', 'is_available', 'vehicle', 'region')
    search_fields = ('user__username', 'full_name', 'phone', 'cin_number', 'vehicle_plate')
    readonly_fields = ('verified_at', 'verified_by', 'position_updated_at', 'cin_preview')
    fieldsets = (
        ('Compte', {'fields': ('user', 'restaurant', 'is_approved', 'is_available', 'admin_notes')}),
        ('Identité (confidentiel)', {'fields': ('full_name', 'photo', 'phone', 'bio', 'cin_number', 'cin_front', 'cin_back',
                                                'cin_preview', 'cin_verified', 'verified_at', 'verified_by')}),
        ('Véhicule', {'fields': ('vehicle', 'vehicle_plate', 'vehicle_photo')}),
        ('Zone & disponibilités', {'fields': ('region', 'zones', 'hours', 'languages', 'years_experience')}),
        ('Paiement', {'fields': ('mm_provider', 'mm_number')}),
        ('Garant', {'fields': ('guarantor_name', 'guarantor_phone')}),
        ('Position', {'fields': ('latitude', 'longitude', 'position_updated_at')}),
    )
    actions = ['approve', 'verify_identity', 'unverify_identity']

    @admin.display(description='CIN')
    def cin_preview(self, obj):
        from django.utils.html import format_html
        parts = []
        for f in (obj.cin_front, obj.cin_back):
            if f:
                parts.append(format_html('<a href="{0}" target="_blank"><img src="{0}" style="max-height:160px;margin-right:8px;border-radius:6px;"></a>', f.url))
        return format_html(''.join(parts)) if parts else '—'

    @admin.action(description='Approuver les livreurs sélectionnés')
    def approve(self, request, queryset):
        queryset.update(is_approved=True)

    @admin.action(description='Marquer l\'identité (CIN) comme vérifiée')
    def verify_identity(self, request, queryset):
        from django.utils import timezone
        queryset.update(cin_verified=True, is_approved=True, verified_at=timezone.now(), verified_by=request.user)

    @admin.action(description='Retirer la vérification d\'identité')
    def unverify_identity(self, request, queryset):
        queryset.update(cin_verified=False, verified_at=None, verified_by=None)


class OrderItemOptionInline(admin.TabularInline):
    model = OrderItemOption
    extra = 0


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('name', 'unit_price', 'quantity', 'line_total', 'note')


class OrderEventInline(admin.TabularInline):
    model = OrderEvent
    extra = 0
    readonly_fields = ('status', 'by', 'note', 'at')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display  = ('number', 'restaurant', 'customer', 'status', 'mode', 'total', 'courier', 'created_at')
    list_filter   = ('status', 'mode', 'payment_method', 'restaurant')
    search_fields = ('number', 'customer__username', 'customer_phone', 'restaurant__name')
    readonly_fields = ('number', 'created_at', 'accepted_at', 'ready_at', 'picked_up_at', 'delivered_at', 'closed_at')
    inlines = [OrderItemInline, OrderEventInline]


admin.site.register(Cart)
admin.site.register(CartItem)


@admin.register(OrderReview)
class OrderReviewAdmin(admin.ModelAdmin):
    list_display  = ('order', 'author', 'author_role', 'target_role', 'rating', 'payment_ok', 'created_at')
    list_filter   = ('author_role', 'target_role', 'rating', 'payment_ok')
    search_fields = ('order__number', 'author__username', 'comment', 'payment_note')
