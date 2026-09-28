from django.urls import path

from .views import (
    CandidateSignupView,
    ResendVerificationView,
    SignupDoneView,
    VerifyEmailView,
)

app_name = "users"

urlpatterns = [
    path("cadastro/", CandidateSignupView.as_view(), name="signup"),
    path("cadastro/enviado/", SignupDoneView.as_view(), name="signup_done"),
    path(
        "verificar-email/reenviar/",
        ResendVerificationView.as_view(),
        name="resend_verification",
    ),
    path(
        "verificar-email/<str:token>/",
        VerifyEmailView.as_view(),
        name="verify_email",
    ),
]
