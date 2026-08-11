from django.contrib import admin

from .models import LegacyOwnershipClaim


@admin.register(LegacyOwnershipClaim)
class LegacyOwnershipClaimAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "application",
        "protocol",
        "status",
        "code_expires_at",
        "verified_at",
        "reviewed_by",
    )
    list_filter = ("status", "created_at")
    search_fields = ("protocol", "contact_email", "contact_tax_id")
    readonly_fields = ("created_at", "updated_at")
