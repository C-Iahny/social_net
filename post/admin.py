from django.contrib import admin
from post.models import Post, Continent, Country, Follow, PostMedia

admin.site.register(Post)
admin.site.register(Continent)
admin.site.register(Country)
admin.site.register(Follow)

@admin.register(PostMedia)
class PostMediaAdmin(admin.ModelAdmin):
    list_display  = ('id', 'post', 'media_type', 'order', 'file')
    list_filter   = ('media_type',)
    raw_id_fields = ('post',)





























