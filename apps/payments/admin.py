from django.contrib import admin

from .models import (
    FeeRequirement,
    ManualPaymentConfirmation,
    PaymentInstrument,
    RefundRequest,
)


class PaymentInstrumentInline(admin.TabularInline):
    model = PaymentInstrument
    extra = 0
    readonly_fields = ("created_at", "updated_at")


@admin.register(FeeRequirement)
class FeeRequirementAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "application",
        "fee_type",
        "base_amount",
        "adjustment_amount",
        "amount",
        "is_waived",
        "created_at",
    )
    list_filter = ("fee_type", "is_waived")
    search_fields = ("application__protocol",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [PaymentInstrumentInline]


@admin.register(PaymentInstrument)
class PaymentInstrumentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "fee_requirement",
        "method",
        "state",
        "amount",
        "active_unique_fee_token",
        "paid_at",
        "created_at",
    )
    list_filter = ("method", "state")
    search_fields = ("fee_requirement__application__protocol",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(ManualPaymentConfirmation)
class ManualPaymentConfirmationAdmin(admin.ModelAdmin):
    list_display = ("id", "payment_instrument", "confirmed_by", "confirmed_at")
    list_filter = ("confirmed_at",)
    readonly_fields = ("created_at",)


@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "application",
        "status",
        "amount",
        "requested_by",
        "approved_by",
        "executed_by",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("application__protocol",)
    readonly_fields = ("created_at", "updated_at")
