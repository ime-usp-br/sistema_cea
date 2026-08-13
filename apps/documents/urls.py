from django.urls import path

from .views import (
    application_firstpage_pdf,
    application_full_pdf,
    payment_receipt_pdf,
    screening_summary_pdf,
)

app_name = "documents"

urlpatterns = [
    path(
        "inscricoes/<str:protocol>/pdf/ficha/",
        application_full_pdf,
        name="application_full_pdf",
    ),
    path(
        "inscricoes/<str:protocol>/pdf/primeira-pagina/",
        application_firstpage_pdf,
        name="application_firstpage_pdf",
    ),
    path(
        "pagamento/instrumento/<int:instrument_id>/pdf/comprovante/",
        payment_receipt_pdf,
        name="payment_receipt_pdf",
    ),
    path(
        "triagem/<int:screening_id>/pdf/resumo/",
        screening_summary_pdf,
        name="screening_summary_pdf",
    ),
]
