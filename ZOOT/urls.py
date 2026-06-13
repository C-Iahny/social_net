"""
URL configuration for ZOOT project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.contrib.auth import views as auth_views



from account.views import (
    register_view,
    login_view,
    logout_view,
    account_view,
    account_search_view,
)
from personal.views import landing_view

urlpatterns = [
    path('admin/', admin.site.urls),
    # ── Internationalisation ───────────────────────────────────────────────────
    # Fournit /i18n/set_language/ (vue POST) pour changer la langue depuis le JS/form
    path('i18n/', include('django.conf.urls.i18n')),
    path('', landing_view, name='landing'),       # Page d'accueil = landing page
    path('feed/', include('post.urls')),           # Le fil d'actualité est déplacé ici
    path('personal/', include('personal.urls')),
    path('account/', include('account.urls', namespace='account')),
    path('friend/', include('friend.urls', namespace='friend')),
    path('chat/', include('chat.urls', namespace='chat')),
    path('stories/', include('stories.urls', namespace='stories')),
    path('notif/', include('notification.urls', namespace='notification')),
    path('groups/', include('group.urls', namespace='group')),
    path('live/',   include('video.urls', namespace='video')),

    path('register/', register_view, name="register"),
    path('login/', login_view, name="login"),
    path('logout/', logout_view, name="logout"),
    path('search/', account_search_view, name="search"),



    # Password reset links (ref: https://github.com/django/django/blob/master/django/contrib/auth/views.py)
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='password_reset/password_change_done.html'), 
        name='password_change_done'),

    path('password_change/', auth_views.PasswordChangeView.as_view(template_name='password_reset/password_change.html'), 
        name='password_change'),

    path('password_reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='password_reset/password_reset_done.html'),
     name='password_reset_done'),

    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='password_reset/password_reset_complete.html'),
     name='password_reset_complete'),





]

# --- Fichiers media ---
# IMPORTANT : django.conf.urls.static.static() retourne [] quand DEBUG=False,
# donc les médias ne sont JAMAIS servis en production avec cette fonction.
# On utilise re_path + serve pour que la route existe dans tous les environnements.
# En production avec Cloudinary, les URLs sont externes (res.cloudinary.com),
# donc cette route ne sera pas utilisée pour les images uploadées via Cloudinary.
# Elle reste utile en dev sans Cloudinary, ou comme fallback.
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
