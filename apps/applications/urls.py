from django.urls import path

from .views import (
    ApplicationDetailView,
    CandidateDashboardView,
    CreateApplicationView,
    TransferSemesterView,
)

app_name = "applications"

urlpatterns = [
    path("painel/", CandidateDashboardView.as_view(), name="dashboard"),
    path("inscricoes/nova/", CreateApplicationView.as_view(), name="create"),
    path(
        "inscricoes/<str:protocol>/transferir-semestre/",
        TransferSemesterView.as_view(),
        name="transfer_semester",
    ),
    path("inscricoes/<str:protocol>/", ApplicationDetailView.as_view(), name="detail"),
]
