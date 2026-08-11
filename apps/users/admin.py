from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import IdentityProviderLink, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "full_name", "email", "codpes", "is_email_verified", "is_staff")
    fieldsets = tuple(UserAdmin.fieldsets or ()) + (
        (
            "Identidade",
            {"fields": ("full_name", "tax_id", "codpes", "is_email_verified", "email_verified_at")},
        ),
    )
    add_fieldsets = tuple(UserAdmin.add_fieldsets or ()) + (
        ("Identidade", {"fields": ("full_name", "tax_id", "codpes", "is_email_verified")}),
    )


@admin.register(IdentityProviderLink)
class IdentityProviderLinkAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "external_id", "external_email", "linked_at")
    list_filter = ("provider",)
    search_fields = ("user__username", "user__email", "external_id", "external_email")
