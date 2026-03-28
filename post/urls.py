from django.urls import path

from .views import (
    Index,
    AddPostView,
    post_feed_view,
    UpdatePostView,
    DeletePostView,
    like_post,
    follow,
    unfollow,
    add_comment,
    delete_comment,
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
    path('comment/<int:comment_id>/delete/', delete_comment, name='delete-comment'),
]
