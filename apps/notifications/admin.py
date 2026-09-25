from django.contrib import admin

from .models import NotificationDispatch, NotificationTemplate


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "description",
        "frequency_display",
        "em_uso",
    )
    list_filter = ("audience", "is_active")
    search_fields = ("code", "name", "description", "subject")
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Frequência")
    def frequency_display(self, obj: NotificationTemplate) -> str:
        """O modelo novo não persiste frequência de disparo (legado tinha
        `sending_frequency`). Retorna ``—`` e mantém o comportamento manual.

        TODO(AI-Assumption): adicionar campo `sending_frequency` ao modelo quando
        a periodicidade for definida pelo negócio.
        """
        return "—"

    @admin.display(boolean=True, description="Em Uso")
    def em_uso(self, obj: NotificationTemplate) -> bool:
        return obj.is_active


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
