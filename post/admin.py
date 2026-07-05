from django.contrib import admin
from post.models import Post, Continent, Country, Follow, PostMedia, Report

admin.site.register(Post)
admin.site.register(Continent)
admin.site.register(Country)
admin.site.register(Follow)

@admin.register(PostMedia)
class PostMediaAdmin(admin.ModelAdmin):
    list_display  = ('id', 'post', 'media_type', 'order', 'file')
    list_filter   = ('media_type',)
    raw_id_fields = ('post',)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display   = ('id', 'reporter', 'content_type', 'object_id', 'reason', 'status', 'created_at')
    list_filter    = ('status', 'reason', 'content_type')
    search_fields  = ('reporter__username',)
    readonly_fields = ('reporter', 'content_type', 'object_id', 'reason', 'comment', 'created_at')
    date_hierarchy = 'created_at'
    actions        = ['mark_reviewed', 'mark_dismissed']

    def mark_reviewed(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='reviewed', reviewed_at=timezone.now())
    mark_reviewed.short_description = 'Marquer comme traité'

    def mark_dismissed(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='dismissed', reviewed_at=timezone.now())
    mark_dismissed.short_description = 'Rejeter le signalement'





























