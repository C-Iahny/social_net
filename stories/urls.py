from django.urls import path
from stories import views

app_name = 'stories'

urlpatterns = [
    path('create/',                     views.create_story,       name='create'),
    path('delete/<int:story_id>/',      views.delete_story,       name='delete'),
    path('viewed/<int:story_id>/',      views.mark_viewed,        name='mark-viewed'),
    path('feed/',                       views.get_feed_stories,   name='feed'),
    path('mine/',                       views.get_my_stories,     name='mine'),
    path('profile/<int:user_id>/',      views.get_profile_stories,name='profile'),
]
