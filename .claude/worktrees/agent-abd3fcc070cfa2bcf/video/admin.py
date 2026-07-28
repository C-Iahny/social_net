from django.contrib import admin
from .models import LiveRoom


@admin.register(LiveRoom)
class LiveRoomAdmin(admin.ModelAdmin):
    list_display  = ('host', 'title', 'status', 'viewer_count', 'created_at', 'ended_at')
    list_filter   = ('status',)
    search_fields = ('host__username', 'title')
    readonly_fields = ('created_at', 'ended_at', 'host_channel')
    actions = ['force_end']

    def force_end(self, request, queryset):
        from django.utils import timezone
        queryset.update(
            status=LiveRoom.STATUS_ENDED,
            ended_at=timezone.now(),
            host_channel='',
            viewer_count=0,
        )
    force_end.short_description = "Terminer les lives sélectionnés"
