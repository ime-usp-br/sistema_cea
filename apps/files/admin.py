from django.contrib import admin

from .models import FileAsset


@admin.register(FileAsset)
class FileAssetAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "original_filename",
        "purpose",
        "size_bytes",
        "application",
        "uploaded_by",
        "created_at",
    )
    list_filter = ("purpose", "created_at")
    search_fields = ("original_filename", "storage_key", "sha256_checksum")
    readonly_fields = ("id", "sha256_checksum", "created_at", "updated_at")
