from django.contrib import admin

from .models import Group, GroupMembership


class GroupMembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 0
    raw_id_fields = ('user',)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'creator', 'privacy', 'member_count', 'created_at')
    list_filter = ('privacy', 'created_at')
    search_fields = ('name', 'description', 'creator__username')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [GroupMembershipInline]


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'group', 'role', 'joined_at')
    list_filter = ('role', 'joined_at')
    search_fields = ('user__username', 'group__name')
    raw_id_fields = ('user', 'group')
