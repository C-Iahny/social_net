from django.urls import path

from .views import (
    Index,
    AddPostView,
    post_feed_view,
    post_feed_more,
    UpdatePostView,
    DeletePostView,
    like_post,
    react_post,
    hashtag_view,
    mention_autocomplete,
    follow,
    unfollow,
    add_comment,
    new_comments,
    delete_comment,
    post_detail,
    repost_post,
    kabary_create,
    vintana_create,
)

app_name = 'post'

urlpatterns = [
    path('index/',        Index,                    name='index'),
    path('',              post_feed_view,           name='post-view'),
    path('add-post/',     AddPostView.as_view(),    name='addPost'),
    path('edit-post/<int:pk>/',   UpdatePostView.as_view(), name='edit-post'),
    path('delete-post/<int:pk>/', DeletePostView.as_view(), name='delete-post'),
    path('like/',         like_post,                name='like-post'),
    path('follow/',       follow,                   name='follow'),
    path('unfollow/',     unfollow,                 name='unfollow'),
    path('comment/<int:post_id>/add/',       add_comment,    name='add-comment'),
    path('comment/<int:post_id>/new/',       new_comments,   name='new-comments'),
    path('comment/<int:comment_id>/delete/', delete_comment, name='delete-comment'),
    path('feed/more/',         post_feed_more,        name='feed-more'),
    path('react/',             react_post,            name='react-post'),
    path('hashtag/<slug:tag>/', hashtag_view,         name='hashtag'),
    path('mention/autocomplete/', mention_autocomplete, name='mention-autocomplete'),
    path('<int:post_id>/',        post_detail,         name='post-detail'),
    path('repost/',                  repost_post,         name='repost'),
    path('kabary/create/',           kabary_create,       name='kabary-create'),
    path('vintana/create/',          vintana_create,      name='vintana-create'),
]
