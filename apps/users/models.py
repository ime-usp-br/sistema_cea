from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model for the USP Starter Kit.

    Starting a project with a custom user model is a Django best practice:
    it allows future fields (e.g. numero_usp) to be added without the
    painful migration required to swap the default user model later.
    """

    class Role(models.TextChoices):
        CANDIDATE = "candidate", "Candidato"
        TEACHER = "teacher", "Docente"
        SECRETARIAT = "secretariat", "Secretaria"
        ADMINISTRATOR = "administrator", "Administrador"

    full_name = models.CharField(max_length=255, blank=True, default="")
    tax_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    codpes = models.IntegerField(unique=True, null=True, blank=True)
    is_email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CANDIDATE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    email = models.EmailField(max_length=255, unique=True)

    class Meta:
        db_table = "users"


class IdentityProviderLink(models.Model):
    """Vínculo de métodos de autenticação ao usuário (Login Híbrido)."""

    class Provider(models.TextChoices):
        LOCAL = "local", "Local"
        USP_SENHA_UNICA = "usp_senha_unica", "Senha Única USP"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="identity_provider_links",
    )
    provider = models.CharField(max_length=50, choices=Provider.choices)
    external_id = models.CharField(max_length=255)
    external_email = models.EmailField(max_length=255, null=True, blank=True)
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "identity_provider_links"
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "external_id"],
                name="uq_identity_provider_links_external",
            ),
            models.UniqueConstraint(
                fields=["user", "provider"],
                name="uq_identity_provider_links_user_provider",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} - {self.provider} ({self.external_id})"
