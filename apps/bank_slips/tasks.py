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


@shared_task
def sync_pending_bank_slips_task() -> int:
    """Consulta o gateway (SOAP ``obterSituacao``) para boletos pendentes.

    Paridade com o cron do legado (``Console/Kernel.php``): a cada ciclo, varre
    os boletos ainda EMITIDOS (status 'E') com instrumento ativo e consulta a
    situação no banco/banco-santander em background. Se o candidato pagou o
    boleto sem acessar o sistema, este poller é o que desbloqueia o fluxo,
    avançando a inscrição (ex.: para ``AWAITING_SCREENING_SCHEDULING``).

    Retorna a quantidade de boletos sincronizados no ciclo.
    """
    from .services import BankSlipPaymentService

    service = BankSlipPaymentService()
    pending = (
        BankSlipPaymentInstrument.objects.select_related(
            "payment_instrument__fee_requirement__application"
        )
        .filter(
            bank_status=BankSlipPaymentInstrument.BankStatus.EMITTED,
            payment_instrument__state__in=[
                PaymentInstrument.State.ACTIVE,
                PaymentInstrument.State.CREATED,
            ],
        )
        .exclude(payment_instrument__state=PaymentInstrument.State.PAID)
    )
    synced = 0
    for slip in pending:
        service.sync_bank_slip_status(slip)
        synced += 1
    return synced
