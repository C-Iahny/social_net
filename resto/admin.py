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
    list_display  = ('user', 'restaurant', 'vehicle', 'region', 'is_approved', 'is_available', 'position_updated_at')
    list_filter   = ('is_approved', 'is_available', 'vehicle', 'region')
    search_fields = ('user__username', 'phone')
    actions = ['approve']

    @admin.action(description='Approuver les livreurs sélectionnés')
    def approve(self, request, queryset):
        queryset.update(is_approved=True)


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
