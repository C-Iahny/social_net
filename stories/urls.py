from django.urls import path
from stories import views

app_name = 'stories'

urlpatterns = [
    path('',                            views.stories_page,         name='page'),
    path('create/',                     views.create_story,         name='create'),
    path('delete/<int:story_id>/',      views.delete_story,         name='delete'),
    path('viewed/<int:story_id>/',      views.mark_viewed,          name='mark-viewed'),
    path('feed/',                       views.get_feed_stories,     name='feed'),
    path('mine/',                       views.get_my_stories,       name='mine'),
    path('profile/<int:user_id>/',      views.get_profile_stories,  name='profile'),
    path('music-search/',               views.music_search,         name='music-search'),
    path('viewers/<int:story_id>/',     views.get_story_viewers,    name='viewers'),
    path('react/<int:story_id>/',       views.story_react,          name='react'),
    path('reply/<int:story_id>/',       views.story_reply,          name='reply'),
]
