from django.urls import path

from .views import (
    ConsultationDecisionView,
    ConsultationListView,
    ConsultationScheduleView,
    SchedulingQueueView,
    ScreeningDecisionView,
    ScreeningListView,
    ScreeningScheduleView,
)

app_name = "meetings"

urlpatterns = [
    # Telas separadas por semestre (paridade com o legado).
    path("triagens/", ScreeningListView.as_view(), name="screening_list"),
    path("reunioes/", ConsultationListView.as_view(), name="consultation_list"),
    # Alias temporário da antiga tela única de Agendamentos.
    path("agendamentos/", SchedulingQueueView.as_view(), name="queue"),
    path(
        "agendamentos/triagem/<str:protocol>/",
        ScreeningScheduleView.as_view(),
        name="screening_schedule",
    ),
    path(
        "agendamentos/reuniao/<str:protocol>/",
        ConsultationScheduleView.as_view(),
        name="consultation_schedule",
    ),
    path(
        "agendamentos/triagem/<int:screening_id>/decisao/",
        ScreeningDecisionView.as_view(),
        name="screening_decision",
    ),
    path(
        "agendamentos/reuniao/<int:meeting_id>/decisao/",
        ConsultationDecisionView.as_view(),
        name="consultation_decision",
    ),
]
