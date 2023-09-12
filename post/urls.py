from django.urls import path, include




from .views import Index, Post_view


app_name = 'post'

urlpatterns = [
	path('index/', Index, name='index'),
	path('post_view/', Post_view.as_view(), name='post_view'),
]

