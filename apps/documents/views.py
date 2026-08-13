from typing import Any

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404

from applications.models import ServiceApplication
from meetings.models import ProjectScreening
from payments.models import PaymentInstrument
from users.models import User

from .services import DocumentRenderingService

_service = DocumentRenderingService()

_STAFF_ROLES = frozenset(
    {User.Role.TEACHER, User.Role.SECRETARIAT, User.Role.ADMINISTRATOR}
)


def _can_access(application: ServiceApplication, user: Any) -> bool:
    return user.is_superuser or user.role in _STAFF_ROLES or application.owner_id == user.pk


def _pdf_response(content: bytes, filename: str) -> HttpResponse:
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def application_full_pdf(request: HttpRequest, protocol: str) -> HttpResponse:
    application = get_object_or_404(
        ServiceApplication.all_objects, protocol=protocol
    )
    user = request.user
    if not _can_access(application, user):
        return HttpResponse(status=403)
    content = _service.render_application_full_pdf(application)
    return _pdf_response(content, f"ficha-{protocol}.pdf")


@login_required
def application_firstpage_pdf(request: HttpRequest, protocol: str) -> HttpResponse:
    application = get_object_or_404(
        ServiceApplication.all_objects, protocol=protocol
    )
    user = request.user
    if not _can_access(application, user):
        return HttpResponse(status=403)
    content = _service.render_application_firstpage_pdf(application)
    return _pdf_response(content, f"resumo-{protocol}.pdf")


@login_required
def payment_receipt_pdf(request: HttpRequest, instrument_id: int) -> HttpResponse:
    instrument = get_object_or_404(PaymentInstrument, pk=instrument_id)
    application = instrument.fee_requirement.application
    user = request.user
    if not _can_access(application, user):
        return HttpResponse(status=403)
    content = _service.render_payment_receipt_pdf(instrument)
    return _pdf_response(content, f"comprovante-{application.protocol}.pdf")


@login_required
def screening_summary_pdf(request: HttpRequest, screening_id: int) -> HttpResponse:
    screening = get_object_or_404(ProjectScreening, pk=screening_id)
    application = screening.application
    user = request.user
    if not _can_access(application, user):
        return HttpResponse(status=403)
    content = _service.render_screening_summary_pdf(screening)
    return _pdf_response(content, f"triagem-{application.protocol}.pdf")
