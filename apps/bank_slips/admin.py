from django.contrib import admin

from .models import BankSlipPaymentInstrument


@admin.register(BankSlipPaymentInstrument)
class BankSlipPaymentInstrumentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "bank_slip_reference",
        "payment_instrument",
        "bank_status",
        "due_date",
        "document_amount",
        "payment_date",
        "cancellation_date",
    )
    list_filter = ("bank_status", "due_date", "registration_date")
    search_fields = ("bank_slip_reference",)
    readonly_fields = ("created_at", "updated_at")
