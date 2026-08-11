from django.urls import path

from .views import (
    DatasetSubmitView,
    RejectedResolutionListView,
    SubmissionResolutionView,
    SubmissionReviewView,
    TeacherReviewQueueView,
)

app_name = "audits"

urlpatterns = [
    path("auditoria/inscricao/<str:protocol>/enviar/", DatasetSubmitView.as_view(), name="submit"),
    path("auditoria/fila/", TeacherReviewQueueView.as_view(), name="teacher_queue"),
    path(
        "auditoria/submissao/<int:submission_id>/revisar/",
        SubmissionReviewView.as_view(),
        name="review",
    ),
    path(
        "auditoria/rejeitadas/",
        RejectedResolutionListView.as_view(),
        name="resolution_list",
    ),
    path(
        "auditoria/submissao/<int:submission_id>/resolver/",
        SubmissionResolutionView.as_view(),
        name="resolve",
    ),
]
