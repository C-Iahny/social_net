from django.urls import path, include
from .views import account_view, edit_account_view, crop_image, global_search_api

app_name = 'account'

urlpatterns = [
    path('<user_id>/',                  account_view,      name="view"),
    path('<user_id>/edit/',             edit_account_view, name="edit"),
    path('<user_id>/edit/cropImage',    crop_image,        name="crop_image"),
    path('search/api/',                 global_search_api, name="search-api"),
]