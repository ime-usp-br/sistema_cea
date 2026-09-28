"""Views de conta do candidato externo (D8)."""

from typing import cast

from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from .forms import (
    CandidateSignupForm,
    EmailVerificationAuthenticationForm,
    ResendVerificationForm,
)
from .services import (
    EmailVerificationError,
    EmailVerificationService,
    RegistrationError,
    RegistrationService,
)

_verification_service = EmailVerificationService()
_registration_service = RegistrationService()


class UserLoginView(LoginView):
    """Login local com mensagem clara para e-mail não confirmado (D8)."""

    template_name = "registration/login.html"
    authentication_form = EmailVerificationAuthenticationForm
    redirect_authenticated_user = True


class CandidateSignupView(View):
    """Cadastro do candidato externo: cria a conta e envia o link de confirmação."""

    template_name = "users/signup.html"

    def get(self, request):
        return render(request, self.template_name, {"form": CandidateSignupForm()})

    def post(self, request):
        form = CandidateSignupForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form}, status=400)
        try:
            user = _registration_service.register(
                full_name=form.cleaned_data["full_name"],
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password1"],
                tax_id=form.cleaned_data.get("tax_id"),
                request=request,
            )
        except RegistrationError as exc:
            form.add_error(None, str(exc))
            return render(request, self.template_name, {"form": form}, status=400)
        return redirect(f"{reverse('users:signup_done')}?email={user.email}")


class SignupDoneView(View):
    """Confirmação de que o cadastro foi criado e o e-mail foi enviado."""

    template_name = "users/signup_done.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {"email": request.GET.get("email", "")},
        )


class VerifyEmailView(View):
    """Confirma o e-mail a partir do token e libera o login local."""

    template_name = "users/verify_email.html"

    def get(self, request, token: str):
        try:
            user = _verification_service.verify(token)
        except EmailVerificationError as exc:
            return render(
                request,
                self.template_name,
                {"success": False, "message": str(exc)},
                status=400,
            )
        return render(
            request,
            self.template_name,
            {
                "success": True,
                "message": "E-mail confirmado com sucesso. Você já pode entrar.",
                "email": user.email,
            },
        )


class ResendVerificationView(View):
    """Reenvia o link de confirmação ("não recebi o e-mail")."""

    template_name = "users/resend_verification.html"

    def get(self, request):
        return render(request, self.template_name, {"form": ResendVerificationForm()})

    def post(self, request):
        form = ResendVerificationForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form}, status=400)
        # Resposta genérica: não revela se o e-mail existe (anti-enumeração).
        _verification_service.resend(
            cast(str, form.cleaned_data["email"]), request
        )
        return render(
            request,
            self.template_name,
            {
                "form": ResendVerificationForm(),
                "sent": True,
            },
        )
