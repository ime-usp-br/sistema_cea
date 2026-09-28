from django.urls import path

from .views import (
    DatasetSubmitView,
    EnableAuditView,
    RejectedResolutionListView,
    SubmissionFileDownloadView,
    SubmissionResolutionView,
    SubmissionReviewView,
    TeacherReviewQueueView,
)

app_name = "audits"

urlpatterns = [
    path("auditoria/inscricao/<str:protocol>/enviar/", DatasetSubmitView.as_view(), name="submit"),
    path(
        "auditoria/inscricao/<str:protocol>/habilitar/",
        EnableAuditView.as_view(),
        name="enable_audit",
    ),
    path("auditoria/fila/", TeacherReviewQueueView.as_view(), name="teacher_queue"),
    path(
        "auditoria/submissao/<int:submission_id>/revisar/",
        SubmissionReviewView.as_view(),
        name="review",
    ),
    path(
        "auditoria/submissao/<int:submission_id>/arquivo/",
        SubmissionFileDownloadView.as_view(),
        name="download_file",
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
