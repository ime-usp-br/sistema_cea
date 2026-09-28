"""Formulários de conta do candidato externo (D8)."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import User


class EmailVerificationAuthenticationForm(AuthenticationForm):
    """Login local que recusa (com mensagem clara) contas sem e-mail confirmado."""

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if username and password:
            user = (
                User.objects.filter(email__iexact=username).first()
                or User.objects.filter(username=username).first()
            )
            if (
                user is not None
                and not user.is_email_verified
                and user.check_password(password)
            ):
                raise forms.ValidationError(
                    "Confirme seu e-mail antes de entrar. Verifique sua caixa de "
                    "entrada ou solicite um novo link.",
                    code="email_not_verified",
                )
        return super().clean()


class CandidateSignupForm(forms.Form):
    """Cadastro do candidato externo (e-mail é o identificador de login)."""

    full_name = forms.CharField(max_length=255, label="Nome completo")
    email = forms.EmailField(max_length=255, label="E-mail")
    tax_id = forms.CharField(max_length=20, required=False, label="CPF/CNPJ (opcional)")
    password1 = forms.CharField(
        label="Senha", widget=forms.PasswordInput, min_length=8
    )
    password2 = forms.CharField(
        label="Confirmação de senha", widget=forms.PasswordInput
    )

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Já existe uma conta com este e-mail.")
        return email

    def clean(self):
        cleaned = super().clean() or {}
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "As senhas não coincidem.")
        return cleaned


class ResendVerificationForm(forms.Form):
    """Reenvio do link de confirmação por e-mail."""

    email = forms.EmailField(max_length=255, label="E-mail")
