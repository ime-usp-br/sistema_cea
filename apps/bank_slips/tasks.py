from celery import shared_task
from django.utils import timezone

from payments.models import FeeRequirement, PaymentInstrument

from .models import BankSlipPaymentInstrument


@shared_task
def regenerate_overdue_bank_slips_task() -> int:
    """Regenera boletos vencidos e notifica os candidatos.

    Substitui o comando cron ``RegenerateAndNotifyPaymentFailure`` do legado:
    encontra boletos com vencimento no passado e ainda ativos, cancela o boleto
    antigo, emite um novo e envia o e-mail ``payment_failure_regenerated``.

    Paridade com o Laravel: o comando legado filtrara exclusivamente os boletos
    cujo ``relativoA = 'Taxa de Inscrição'``. Assim, boletos de Taxa de Projeto
    (R$ 250) e Complemento (R$ 60) NÃO devem ser regenerados automaticamente
    (Gap D), pois possuem prazos/negociações diferenciadas com os docentes.
    """
    from .services import BankSlipPaymentService

    service = BankSlipPaymentService()
    today = timezone.localdate()
    overdue = (
        BankSlipPaymentInstrument.objects.select_related(
            "payment_instrument__fee_requirement__application"
        )
        .filter(
            due_date__lt=today,
            bank_status=BankSlipPaymentInstrument.BankStatus.EMITTED,
            payment_instrument__state__in=[
                PaymentInstrument.State.ACTIVE,
                PaymentInstrument.State.CREATED,
            ],
            payment_instrument__fee_requirement__fee_type=(
                FeeRequirement.FeeType.APPLICATION_FEE
            ),
        )
        .exclude(payment_instrument__state=PaymentInstrument.State.PAID)
    )
    regenerated = 0
    for slip in overdue:
        service.regenerate_slip(
            slip, notify_template_code="payment_failure_regenerated"
        )
        regenerated += 1
    return regenerated
