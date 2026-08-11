from django.contrib import admin

from .models import NotificationDispatch, NotificationTemplate


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "code",
        "name",
        "audience",
        "is_active",
    )
    list_filter = ("audience", "is_active")
    search_fields = ("code", "name", "description", "subject")
    readonly_fields = ("created_at", "updated_at")


@admin.register(NotificationDispatch)
class NotificationDispatchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "template",
        "application",
        "recipient_email",
        "status",
        "sent_at",
        "created_at",
    )
    list_filter = ("status", "template", "sent_at")
    search_fields = ("recipient_email", "template__code", "application__protocol")
    readonly_fields = ("created_at", "updated_at")
