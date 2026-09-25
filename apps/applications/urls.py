from django.urls import path

from .views import (
    ApplicationDeletedListView,
    ApplicationDeleteView,
    ApplicationDetailView,
    ApplicationListView,
    ApplicationModalityChangeView,
    ApplicationRestoreView,
    CandidateDashboardView,
    CreateApplicationView,
    EventListView,
    TransferSemesterView,
)

app_name = "applications"

urlpatterns = [
    path("painel/", CandidateDashboardView.as_view(), name="dashboard"),
    path("inscricoes/nova/", CreateApplicationView.as_view(), name="create"),
    path("inscricoes/", ApplicationListView.as_view(), name="list"),
    path("inscricoes/excluidas/", ApplicationDeletedListView.as_view(), name="deleted_list"),
    path(
        "inscricoes/<str:protocol>/restaurar/",
        ApplicationRestoreView.as_view(),
        name="restore",
    ),
    path("inscricoes/historico/", EventListView.as_view(), name="event_list"),
    path(
        "inscricoes/<str:protocol>/modalidade/",
        ApplicationModalityChangeView.as_view(),
        name="modality_change",
    ),
    path(
        "inscricoes/<str:protocol>/excluir/",
        ApplicationDeleteView.as_view(),
        name="delete",
    ),
    path(
        "inscricoes/<str:protocol>/transferir-semestre/",
        TransferSemesterView.as_view(),
        name="transfer_semester",
    ),
    path("inscricoes/<str:protocol>/", ApplicationDetailView.as_view(), name="detail"),
]
