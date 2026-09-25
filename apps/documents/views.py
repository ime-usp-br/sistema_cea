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

_FULL_PDF_ROLES = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})
_FIRSTPAGE_PDF_ROLES = frozenset(
    {User.Role.TEACHER, User.Role.SECRETARIAT, User.Role.ADMINISTRATOR}
)


def _is_staff(user: Any, roles: frozenset) -> bool:
    return user.is_superuser or user.role in roles


def _can_full_pdf(user: Any) -> bool:
    return _is_staff(user, _FULL_PDF_ROLES)


def _can_firstpage_pdf(user: Any) -> bool:
    return _is_staff(user, _FIRSTPAGE_PDF_ROLES)


def _can_access_owner_or_staff(application: ServiceApplication, user: Any) -> bool:
    return _is_staff(user, _FIRSTPAGE_PDF_ROLES) or application.owner_id == user.pk


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
    if not _can_full_pdf(user):
        return HttpResponse(status=403)
    content = _service.render_application_full_pdf(application)
    return _pdf_response(content, f"ficha-{protocol}.pdf")


@login_required
def application_firstpage_pdf(request: HttpRequest, protocol: str) -> HttpResponse:
    application = get_object_or_404(
        ServiceApplication.all_objects, protocol=protocol
    )
    user = request.user
    if not _can_firstpage_pdf(user):
        return HttpResponse(status=403)
    can_view_financial = bool(
        user.is_superuser
        or (
            hasattr(user, "role")
            and user.role  # type: ignore[union-attr]
            in {User.Role.SECRETARIAT, User.Role.ADMINISTRATOR}
        )
        or application.owner_id == user.pk
    )
    content = _service.render_application_firstpage_pdf(
        application, can_view_financial=can_view_financial
    )
    return _pdf_response(content, f"resumo-{protocol}.pdf")


@login_required
def application_attachment_download(request: HttpRequest, attachment_id: int) -> HttpResponse:
    from django.core.files.storage import default_storage
    from django.http import Http404

    from applications.models import ApplicationAttachment

    attachment = get_object_or_404(
        ApplicationAttachment.objects.select_related("file_asset", "application"),
        pk=attachment_id,
    )
    user = request.user
    application = attachment.application
    if not _can_access_owner_or_staff(application, user):
        return HttpResponse(status=403)
    asset = attachment.file_asset
    try:
        content = default_storage.open(asset.storage_key, "rb").read()
    except FileNotFoundError as exc:
        raise Http404("Arquivo indisponível.") from exc
    response = HttpResponse(
        content, content_type=asset.content_type or "application/octet-stream"
    )
    response["Content-Disposition"] = f'attachment; filename="{asset.original_filename}"'
    return response


@login_required
def payment_receipt_pdf(request: HttpRequest, instrument_id: int) -> HttpResponse:
    instrument = get_object_or_404(PaymentInstrument, pk=instrument_id)
    application = instrument.fee_requirement.application
    user = request.user
    if not _can_access_owner_or_staff(application, user):
        return HttpResponse(status=403)
    content = _service.render_payment_receipt_pdf(instrument)
    return _pdf_response(content, f"comprovante-{application.protocol}.pdf")


@login_required
def screening_summary_pdf(request: HttpRequest, screening_id: int) -> HttpResponse:
    screening = get_object_or_404(ProjectScreening, pk=screening_id)
    application = screening.application
    user = request.user
    if not _can_access_owner_or_staff(application, user):
        return HttpResponse(status=403)
    content = _service.render_screening_summary_pdf(screening)
    return _pdf_response(content, f"triagem-{application.protocol}.pdf")
