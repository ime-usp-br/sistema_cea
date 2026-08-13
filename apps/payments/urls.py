from django.urls import path

from .views import (
    FeePaymentView,
    ManualPaymentConfirmationView,
    OverdueBillingListView,
    OverdueReminderView,
    RefundActionView,
    RefundRequestCreateView,
    RefundRequestListView,
)

app_name = "payments"

urlpatterns = [
    path(
        "pagamento/inscricao/<str:protocol>/",
        FeePaymentView.as_view(),
        name="fee_payment",
    ),
    path(
        "pagamento/instrumento/<int:instrument_id>/confirmar-manual/",
        ManualPaymentConfirmationView.as_view(),
        name="manual_confirmation",
    ),
    path("reembolsos/", RefundRequestListView.as_view(), name="refund_list"),
    path(
        "reembolsos/inscricao/<str:protocol>/solicitar/",
        RefundRequestCreateView.as_view(),
        name="refund_create",
    ),
    path(
        "reembolsos/<int:refund_id>/<str:action>/",
        RefundActionView.as_view(),
        name="refund_action",
    ),
    path("cobrancas/vencidos/", OverdueBillingListView.as_view(), name="overdue_list"),
    path("cobrancas/vencidos/lembrete/", OverdueReminderView.as_view(), name="overdue_remind"),
]
