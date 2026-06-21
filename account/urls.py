from django.urls import path, include
from .views import (
    account_view, edit_account_view, crop_image,
    global_search_api, profile_posts_more, update_cover_image,
    phone_send_otp, phone_verify_otp,
)

app_name = 'account'

urlpatterns = [
    path('<user_id>/',                  account_view,        name="view"),
    path('<user_id>/edit/',             edit_account_view,   name="edit"),
    path('<user_id>/edit/cropImage',    crop_image,          name="crop_image"),
    path('<user_id>/posts/more/',       profile_posts_more,  name="profile-posts-more"),
    path('search/api/',                 global_search_api,   name="search-api"),
    path('cover/update/',              update_cover_image,  name="update-cover"),
    # ── Vérification téléphone ─────────────────────────────────────────────
    path('phone/envoyer-code/',        phone_send_otp,      name="phone-send-otp"),
    path('phone/verifier/',            phone_verify_otp,    name="phone-verify-otp"),
]