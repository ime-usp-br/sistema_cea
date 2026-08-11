from django.contrib import admin

from .models import PixPaymentInstrument, PixWebhookEvent


@admin.register(PixPaymentInstrument)
class PixPaymentInstrumentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "pix_reference",
        "payment_instrument",
        "external_status",
        "generated_at",
        "expires_at",
        "paid_at",
    )
    list_filter = ("external_status", "generated_at")
    search_fields = ("pix_reference", "payer_name", "payer_tax_id")
    readonly_fields = ("created_at", "updated_at")


@admin.register(PixWebhookEvent)
class PixWebhookEventAdmin(admin.ModelAdmin):
    list_display = ("id", "pix_reference", "token_valid", "processed", "received_at")
    list_filter = ("token_valid", "processed", "received_at")
    search_fields = ("pix_reference",)
    readonly_fields = ("received_at",)
