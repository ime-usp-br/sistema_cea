from django.urls import path

from .views import (
    ClaimApproveView,
    ClaimConfirmView,
    ClaimQueueView,
    ClaimRequestView,
)

app_name = "imports"

urlpatterns = [
    path("vincular-inscricao/", ClaimRequestView.as_view(), name="claim_request"),
    path(
        "vincular-inscricao/confirmar/",
        ClaimConfirmView.as_view(),
        name="claim_confirm",
    ),
    path("gestao/resgates/", ClaimQueueView.as_view(), name="claim_queue"),
    path(
        "gestao/resgates/<int:claim_id>/aprovar/",
        ClaimApproveView.as_view(),
        name="claim_approve",
    ),
]
