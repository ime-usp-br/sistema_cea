from django.contrib import admin

from .models import (
    ApplicationAttachment,
    ApplicationCatalogSelection,
    CatalogOption,
    ServiceApplication,
)


class ApplicationCatalogSelectionInline(admin.TabularInline):
    model = ApplicationCatalogSelection
    extra = 0
    autocomplete_fields = ("option",)


class ApplicationAttachmentInline(admin.TabularInline):
    model = ApplicationAttachment
    extra = 0
    readonly_fields = ("file_asset", "created_at")


@admin.register(CatalogOption)
class CatalogOptionAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "category", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("code", "label")


@admin.register(ServiceApplication)
class ServiceApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "protocol",
        "term",
        "owner",
        "modality",
        "lifecycle_status",
        "payment_state",
        "dataset_audit_required",
        "origin",
        "created_at",
    )
    list_filter = ("modality", "lifecycle_status", "origin", "dataset_audit_required")
    search_fields = ("protocol", "researcher_name", "contact_email", "tax_id")
    readonly_fields = ("protocol", "created_at", "updated_at")
    inlines = [ApplicationCatalogSelectionInline, ApplicationAttachmentInline]


@admin.register(ApplicationCatalogSelection)
class ApplicationCatalogSelectionAdmin(admin.ModelAdmin):
    list_display = ("application", "option", "other_text")
    list_filter = ("option__category",)
    autocomplete_fields = ("application", "option")


@admin.register(ApplicationAttachment)
class ApplicationAttachmentAdmin(admin.ModelAdmin):
    list_display = ("application", "file_asset", "description", "created_at")
    autocomplete_fields = ("application", "file_asset")
