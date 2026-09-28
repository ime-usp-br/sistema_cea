"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
from django.contrib.auth import views as auth_views
from django.urls import include, path

from base.views import index, logout_view
from users.views import UserLoginView

urlpatterns = [
    path('admin/', admin.site.urls),
    # Autenticação local (D8): login customizado (mensagem de e-mail não
    # confirmado) + fluxo de recuperação de senha do Django com templates
    # próprios em templates/registration/.
    path('auth/login/', UserLoginView.as_view(), name='login'),
    path(
        'auth/password_reset/',
        auth_views.PasswordResetView.as_view(
            template_name='registration/password_reset_form.html',
            email_template_name='registration/password_reset_email.html',
            subject_template_name='registration/password_reset_subject.txt',
        ),
        name='password_reset',
    ),
    path(
        'auth/password_reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='registration/password_reset_done.html'
        ),
        name='password_reset_done',
    ),
    path(
        'auth/reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html'
        ),
        name='password_reset_confirm',
    ),
    path(
        'auth/reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='registration/password_reset_complete.html'
        ),
        name='password_reset_complete',
    ),
    path(
        'auth/password_change/',
        auth_views.PasswordChangeView.as_view(
            template_name='registration/password_change_form.html'
        ),
        name='password_change',
    ),
    path(
        'auth/password_change/done/',
        auth_views.PasswordChangeDoneView.as_view(
            template_name='registration/password_change_done.html'
        ),
        name='password_change_done',
    ),
    path('', index, name='index'),
    path('', include('users.urls')),
    path('', include('applications.urls')),
    path('', include('audits.urls')),
    path('', include('payments.urls')),
    path('', include('pix.urls')),
    path('', include('bank_slips.urls')),
    path('', include('meetings.urls')),
    path('', include('documents.urls')),
    path('', include('reports.urls')),
    path('', include('imports.urls')),
    path('logout/', logout_view, name='logout'),
    path('', include('senhaunica_socialite.urls')),
]
