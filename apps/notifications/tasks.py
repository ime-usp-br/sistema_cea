from typing import Any

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template import Context, Template
from django.utils import timezone

from .models import NotificationDispatch, NotificationTemplate


@shared_task
def send_notification_task(
    template_code: str,
    recipient_email: str,
    context_data: dict[str, Any],
    application_id: int | None = None,
) -> NotificationDispatch | None:
    """Envia um e-mail a partir de um template canônico ativo.

    Se o template estiver inativo ou não existir, interrompe sem enviar
    (TS-NOT-009). Em caso de falha, registra o despacho como ``failed``
    (TS-NOT-010).
    """
    template = NotificationTemplate.objects.filter(
        code=template_code, is_active=True
    ).first()
    if template is None:
        return None

    application = None
    if application_id is not None:
        from applications.models import ServiceApplication

        application = ServiceApplication.objects.filter(pk=application_id).first()

    dispatch = NotificationDispatch.objects.create(
        template=template,
        application=application,
        recipient_email=recipient_email,
        status=NotificationDispatch.Status.PENDING,
    )

    try:
        context = Context(context_data)
        subject = Template(template.subject).render(context)
        body = Template(template.body).render(context)
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
    except Exception as exc:  # noqa: BLE001 - registra qualquer falha de envio
        dispatch.status = NotificationDispatch.Status.FAILED
        dispatch.error_message = str(exc)
        dispatch.save(update_fields=["status", "error_message", "updated_at"])
        return dispatch

    dispatch.status = NotificationDispatch.Status.SENT
    dispatch.sent_at = timezone.now()
    dispatch.save(update_fields=["status", "sent_at", "updated_at"])
    return dispatch
