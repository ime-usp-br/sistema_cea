from django.urls import path

from .views import (
    GeneratePixView,
    PixDetailView,
    PixQrCodeImageView,
    pix_webhook,
)

app_name = "pix"

urlpatterns = [
    path("webhooks/pix/", pix_webhook, name="webhook"),
    path(
        "pagamento/inscricao/<str:protocol>/pix/gerar/",
        GeneratePixView.as_view(),
        name="generate",
    ),
    path(
        "pagamento/inscricao/<str:protocol>/pix/",
        PixDetailView.as_view(),
        name="detail",
    ),
    path(
        "pix/<int:pix_id>/qrcode/",
        PixQrCodeImageView.as_view(),
        name="qrcode_image",
    ),
]
