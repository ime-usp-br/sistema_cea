from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import IdentityProviderLink, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("full_name", "codpes", "email", "role")
    list_filter = ("role", "is_staff", "is_superuser", "is_email_verified")
    search_fields = ("username", "full_name", "email", "codpes")
    radio_fields = {"role": admin.HORIZONTAL}
    fieldsets = tuple(UserAdmin.fieldsets or ()) + (
        (
            "Perfil",
            {"fields": ("role", "full_name", "tax_id", "codpes", "is_email_verified", "email_verified_at")},
        ),
    )
    add_fieldsets = tuple(UserAdmin.add_fieldsets or ()) + (
        ("Perfil", {"fields": ("role", "full_name", "tax_id", "codpes", "is_email_verified")}),
    )


@admin.register(IdentityProviderLink)
class IdentityProviderLinkAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "external_id", "external_email", "linked_at")
    list_filter = ("provider",)
    search_fields = ("user__username", "user__email", "external_id", "external_email")
