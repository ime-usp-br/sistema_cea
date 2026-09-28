from django.apps import AppConfig


class TermsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "terms"

    def ready(self) -> None:
        from . import signals  # noqa: F401
