from django.urls import path

from .views import (
    AdminRegenerateBankSlipView,
    BankSlipDetailView,
    BankSlipDownloadPdfView,
    GenerateBankSlipView,
)

app_name = "bank_slips"

urlpatterns = [
    path(
        "pagamento/inscricao/<str:protocol>/boleto/gerar/",
        GenerateBankSlipView.as_view(),
        name="generate",
    ),
    path(
        "pagamento/inscricao/<str:protocol>/boleto/",
        BankSlipDetailView.as_view(),
        name="detail",
    ),
    path(
        "boleto/<int:slip_id>/pdf/",
        BankSlipDownloadPdfView.as_view(),
        name="download_pdf",
    ),
    path(
        "boleto/<int:slip_id>/regenerar/",
        AdminRegenerateBankSlipView.as_view(),
        name="admin_regenerate",
    ),
]
