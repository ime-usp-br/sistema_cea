"""Comando de gestão para simular e inspecionar a jornada completa de uma inscrição.

Avança o fluxo (inscrição → pagamento → auditoria → triagem/reunião → estado
final) passo a passo via flags, usando a camada de serviço real e mockando
apenas os gateways externos (Pix e Boleto). O objetivo é percorrer cada estágio
em desenvolvimento e verificar o que está funcionando e o que não está.

Exemplos:
    docker compose exec web python manage.py simulate_journey --submit
    docker compose exec web python manage.py simulate_journey --submit --pay
    docker compose exec web python manage.py simulate_journey --submit --pay \
        --submit-dataset --review approved --schedule-screening \
        --screening-decision approved_as_project --pay
    docker compose exec web python manage.py simulate_journey --all \
        --modality project --method pix
    docker compose exec web python manage.py simulate_journey --step 4
"""

from __future__ import annotations

import base64
import tempfile
import time
import uuid
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import override_settings

SIM_USERNAME = "sim_candidate"
SIM_TEACHER_USERNAME = "sim_teacher"
SIM_SECRETARIAT_USERNAME = "sim_secretariat"
SIM_PASSWORD = "sim-senha-123"

_QR_PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


class Command(BaseCommand):
    help = "Simula a jornada completa de uma inscrição, etapa por etapa, via flags."

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._candidate: Any = None
        self._teacher: Any = None
        self._secretariat: Any = None
        self._application: Any = None

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--modality",
            default="project",
            choices=["project", "consultation"],
            help="Modalidade da inscrição (padrão: project).",
        )
        parser.add_argument(
            "--submit",
            action="store_true",
            help="Cria a inscrição (taxa de inscrição gerada, await_payment).",
        )
        parser.add_argument(
            "--pay",
            action="store_true",
            help="Paga a próxima taxa pendente (inscrição ou projeto).",
        )
        parser.add_argument(
            "--method",
            default="pix",
            choices=["pix", "boleto", "manual"],
            help="Forma de pagamento usada pelo --pay (padrão: pix).",
        )
        parser.add_argument(
            "--submit-dataset",
            action="store_true",
            help="Projeto: envia os dados para auditoria.",
        )
        parser.add_argument(
            "--channel",
            default="file",
            choices=["file", "external_link"],
            help="Canal da submissão de auditoria (padrão: file).",
        )
        parser.add_argument(
            "--dataset-url",
            default="https://drive.example.com/dados-simulados",
            help="URL externa usada quando --channel=external_link.",
        )
        parser.add_argument(
            "--review",
            choices=["approved", "needs_correction", "rejected"],
            help="Revisa a submissão de auditoria (padrão no --step: approved).",
        )
        parser.add_argument(
            "--resolve",
            choices=[
                "convert_to_consultation",
                "reject_application",
                "transfer_term",
            ],
            help="Resolve a rejeição de auditoria.",
        )
        parser.add_argument(
            "--target-term",
            type=int,
            default=None,
            help="PK do período alvo para --resolve transfer_term.",
        )
        parser.add_argument(
            "--schedule-screening",
            action="store_true",
            help="Projeto: agenda a triagem.",
        )
        parser.add_argument(
            "--screening-decision",
            choices=[
                "approved_as_project",
                "approved_as_consultation",
                "not_approved",
            ],
            help="Registra a decisão da triagem (padrão no --step: approved_as_project).",
        )
        parser.add_argument(
            "--schedule-consultation",
            action="store_true",
            help="Consulta: agenda a reunião de consulta.",
        )
        parser.add_argument(
            "--consultation-decision",
            choices=[
                "approved_as_project",
                "approved_as_consultation",
                "not_approved",
            ],
            help="Registra a decisão da reunião (padrão no --step: approved_as_consultation).",
        )
        parser.add_argument(
            "--screening-feedback",
            choices=[
                "screening_completed",
                "screening_not_completed",
            ],
            help="Projeto: registra o feedback do docente da triagem "
            "(padrão no --step: screening_completed).",
        )
        parser.add_argument(
            "--consultation-feedback",
            choices=[
                "consultation_completed",
                "consultation_not_completed",
            ],
            help="Consulta: registra o feedback do docente da reunião "
            "(padrão no --step: consultation_completed).",
        )
        parser.add_argument(
            "--refund",
            action="store_true",
            help="Cria, aprova e executa um reembolso do valor pago.",
        )
        parser.add_argument(
            "--step",
            type=int,
            default=None,
            help="Executa apenas a etapa N da sequência canônica da modalidade.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Executa a jornada completa até o estado final.",
        )
        parser.add_argument(
            "--status",
            action="store_true",
            help="Imprime o estado atual da inscrição mais recente.",
        )
        parser.add_argument(
            "--protocol",
            default=None,
            help="Protocolo da inscrição alvo (padrão: mais recente do usuário simulado).",
        )
        parser.add_argument(
            "--owner",
            default=SIM_USERNAME,
            help="Username do candidato dono da inscrição (padrão: sim_candidate).",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=0.0,
            help="Pausa (segundos) entre etapas no modo --all.",
        )

    # ------------------------------------------------------------------
    # Fluxo principal
    # ------------------------------------------------------------------

    def handle(self, *args: Any, **options: Any) -> None:
        # O bind mount /app pertence ao usuário do host, e o container roda como
        # uid 1000: isola os arquivos de mídia da simulação em um diretório
        # temporário (mesmo padrão dos testes) para não depender de permissões.
        media_root = tempfile.mkdtemp(prefix="cea-simulacao-media-")
        with override_settings(MEDIA_ROOT=media_root):
            self._bootstrap_actors(options)
            self._application = None

            if options["all"]:
                self._run_all(options)
                return

            step = options["step"]
            if step is not None:
                steps = self._canonical_steps(options["modality"])
                if not 1 <= step <= len(steps):
                    raise CommandError(f"--step deve estar entre 1 e {len(steps)}.")
                label, fn = steps[step - 1]
                self.stdout.write(f"\n[{step}] {label}")
                fn(options)
            else:
                requested = [
                    ("submit", self._action_submit),
                    ("pay", self._action_pay),
                    ("submit_dataset", self._action_submit_dataset),
                    ("review", self._action_review),
                    ("resolve", self._action_resolve),
                    ("schedule_screening", self._action_schedule_screening),
                    ("screening_feedback", self._action_screening_feedback),
                    ("screening_decision", self._action_screening_decision),
                    ("schedule_consultation", self._action_schedule_consultation),
                    ("consultation_feedback", self._action_consultation_feedback),
                    ("consultation_decision", self._action_consultation_decision),
                    ("refund", self._action_refund),
                ]
                ran_any = False
                for name, fn in requested:
                    if options.get(name):
                        fn(options)
                        ran_any = True
                if not ran_any:
                    if options.get("status"):
                        self._require_application(options)
                    else:
                        self.stdout.write(self.style.NOTICE("Nenhuma ação informada. Use --help para ver as opções."))

            if self._application is None:
                return
            self._print_status(self._application)

    def _run_all(self, options: Any) -> None:
        steps = self._canonical_steps(options["modality"])
        self.stdout.write(self.style.MIGRATE_HEADING("\nJornada completa simulada"))
        current: Any = None
        for label, fn in steps:
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write(self.style.MIGRATE_HEADING(label))
            try:
                current = fn(options)
            except Exception as exc:  # noqa: BLE001 - falha propagada como relatório
                self.stdout.write(self.style.ERROR(f"Falha nesta etapa: {exc}"))
                if current is not None:
                    self._print_status(current)
                raise CommandError("Jornada interrompida. Antes de repetir, verifique o erro acima.") from exc
            if current is not None:
                self._print_status(current)
            if options["interval"]:
                time.sleep(float(options["interval"]))

    def _canonical_steps(self, modality: str) -> list[tuple[str, Any]]:
        """Sequência canônica (caminho feliz) para --step e --all.

        O feedback do docente e a decisão são operações separadas e feitas por
        perfis distintos: o docente registra o feedback; a secretaria registra
        a decisão (ARCHITECTURE.md §7.3/§7.4).
        """
        common_start = [
            ("1. Submissão da inscrição (taxa gerada, awaiting_payment)", self._action_submit),
            ("2. Pagamento da taxa de inscrição", self._action_pay),
        ]
        if modality == "consultation":
            return common_start + [
                ("3. Agendamento da reunião de consulta", self._action_schedule_consultation),
                ("4. Feedback do docente (reunião realizada)", self._action_consultation_feedback),
                ("5. Decisão da secretaria: aprovado como consulta", self._action_consultation_decision),
            ]
        return common_start + [
            ("3. Envio dos dados para auditoria", self._action_submit_dataset),
            ("4. Revisão docente (aprova)", self._action_review),
            ("5. Agendamento da triagem", self._action_schedule_screening),
            ("6. Feedback do docente (triagem realizada)", self._action_screening_feedback),
            ("7. Decisão da secretaria: aprovado como projeto (taxa R$ 250)", self._action_screening_decision),
            ("8. Pagamento da taxa de projeto", self._action_pay),
        ]

    # ------------------------------------------------------------------
    # Setup do ambiente simulado
    # ------------------------------------------------------------------

    def _bootstrap_actors(self, options: Any) -> None:
        from users.models import User

        owner_username = (options.get("owner") or SIM_USERNAME).strip() or SIM_USERNAME
        self._candidate = self._get_or_create_user(
            owner_username,
            User.Role.CANDIDATE,
            "Candidato(a) de Simulação",
            f"{owner_username}@example.com",
            reset_password=owner_username == SIM_USERNAME,
        )
        self._teacher = self._get_or_create_user(
            SIM_TEACHER_USERNAME,
            User.Role.TEACHER,
            "Docente de Simulação",
            "sim_teacher@example.com",
        )
        self._secretariat = self._get_or_create_user(
            SIM_SECRETARIAT_USERNAME,
            User.Role.SECRETARIAT,
            "Secretaria de Simulação",
            "sim_secretariat@example.com",
        )

    def _get_or_create_user(
        self,
        username: str,
        role: str,
        full_name: str,
        email: str,
        reset_password: bool = False,
    ) -> Any:
        from users.models import User

        user = User.objects.filter(username=username).first()
        if user is not None:
            if reset_password:
                user.set_password(SIM_PASSWORD)
                user.save(update_fields=["password", "updated_at"])
            return user
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            role=role,
            is_active=True,
            is_email_verified=True,
        )
        user.set_password(SIM_PASSWORD)
        user.save()
        self.stdout.write(self.style.SUCCESS(f"Usuário criado: {username} (senha: {SIM_PASSWORD})"))
        return user

    def _ensure_term(self, options: Any) -> Any:
        from datetime import date

        from terms.models import AcademicTerm

        year = date.today().year + 1
        term, created = AcademicTerm.objects.get_or_create(
            year=year,
            period=AcademicTerm.Period.FIRST,
            defaults={"submission_start_date": date.today()},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Período letivo criado: {term}"))
        from applications.models import CatalogOption

        if CatalogOption.objects.count() == 0:
            raise CommandError(
                "Nenhuma opção de catálogo encontrada. Execute as migrações "
                "(manage.py migrate) para popular catalog_options."
            )
        return term

    def _next_term(self, current: Any) -> Any:
        from terms.models import AcademicTerm

        ordered = list(AcademicTerm.objects.order_by("year", "period"))
        for index, term in enumerate(ordered):
            if term.pk == current.pk and index + 1 < len(ordered):
                return ordered[index + 1]
        if current.period == AcademicTerm.Period.FIRST:
            return AcademicTerm.objects.get_or_create(
                year=current.year,
                period=AcademicTerm.Period.SECOND,
                defaults={"submission_start_date": current.submission_start_date},
            )[0]
        return AcademicTerm.objects.get_or_create(
            year=current.year + 1,
            period=AcademicTerm.Period.FIRST,
            defaults={"submission_start_date": current.submission_start_date},
        )[0]

    # ------------------------------------------------------------------
    # Alvo da simulação
    # ------------------------------------------------------------------

    def _require_application(self, options: Any) -> Any:
        if self._application is not None:
            return self._application
        from applications.models import ServiceApplication

        if options.get("protocol"):
            application = ServiceApplication.all_objects.filter(protocol=options["protocol"]).first()
            if application is None:
                raise CommandError(f"Nenhuma inscrição com protocolo {options['protocol']}.")
            self._application = application
            return application
        application = (
            ServiceApplication.objects.filter(owner=self._candidate, modality=options["modality"])
            .order_by("-created_at")
            .first()
        )
        if application is None:
            raise CommandError(
                "Nenhuma inscrição encontrada para o candidato simulado. Execute --submit antes ou informe --protocol."
            )
        self._application = application
        return application

    def _set_application(self, application: Any) -> Any:
        self._application = application
        return application

    # ------------------------------------------------------------------
    # Etapas da jornada
    # ------------------------------------------------------------------

    def _action_submit(self, options: Any) -> Any:
        term = self._ensure_term(options)
        from applications.factories import build_valid_form_payload, service_kwargs_from_payload
        from applications.services import ApplicationSubmissionService

        payload = build_valid_form_payload(modality=options["modality"], term_pk=term.pk)
        kwargs = service_kwargs_from_payload(payload, term)
        application = ApplicationSubmissionService().create_application(owner=self._candidate, **kwargs)
        self._print_event("Inscrição criada", application)
        return self._set_application(application)

    def _action_pay(self, options: Any) -> Any:
        application = self._require_application(options)
        method = options["method"]
        method_label = "pix" if method == "pix" else "boleto" if method == "boleto" else "confirmação manual"
        paid_any = False
        while True:
            fee = next(
                (f for f in application.fee_requirements.all() if not f.is_waived and not f.is_paid),
                None,
            )
            if fee is None:
                break
            if method == "manual":
                self._pay_manually(fee)
            elif method == "pix":
                self._pay_with_pix(fee)
            else:
                self._pay_with_bank_slip(fee)
            application.refresh_from_db()
            self._print_event(
                f"{fee.get_fee_type_display()} paga ({method_label})",
                application,
            )
            paid_any = True
        if not paid_any:
            self.stdout.write(self.style.WARNING("Nenhuma taxa pendente de pagamento."))
        return application

    def _pay_manually(self, fee: Any) -> None:
        from payments.services import ManualPaymentService, PaymentOrchestrationService

        instrument = PaymentOrchestrationService().create_payment_instrument(
            fee_requirement=fee, method="pix", created_by=self._candidate
        )
        ManualPaymentService().confirm_manual_payment(
            instrument=instrument,
            confirmed_by=self._secretariat,
            note="Pagamento simulado de forma manual.",
        )

    def _pay_with_pix(self, fee: Any) -> None:
        from unittest.mock import patch

        from pix.services import PixPaymentService, format_ptbr_amount

        pix_result = {
            "idfpix": f"pix-sim-{uuid.uuid4().hex[:12]}",
            "qrCode": "00020126580014br.gov.bcb.pix0136simulacao000000",
            "qrCodeImgBase64": base64.b64encode(_QR_PLACEHOLDER_PNG),
            "status": "ativo",
            "expiracao": settings.PIX_EXPIRATION_SECONDS,
        }
        with patch("pix.gateways.PixGateway.generate_pix", return_value=pix_result):
            pix = PixPaymentService().generate_pix_for_fee(fee_requirement=fee, created_by=self._candidate)
        # Confirmação pelo caminho real do webhook (idempotente), sem rede.
        service = PixPaymentService()
        event = service.process_webhook_payload(
            raw_payload={
                "idfpix": pix.pix_reference,
                "status": "Pago",
                "valor": format_ptbr_amount(fee.amount),
            },
            token=settings.PIX_WEBHOOK_TOKEN,
        )
        if event.error_message is not None:
            raise CommandError(f"Webhook Pix não confirmou o pagamento: {event.error_message}.")

    def _pay_with_bank_slip(self, fee: Any) -> None:
        from unittest.mock import patch

        from bank_slips.services import BankSlipPaymentService

        if not settings.DEBUG and not getattr(settings, "DJANGO_ENV", "") == "development":
            raise CommandError("A simulação de pagamento de boleto exige DEBUG=True (ou use --method pix/manual).")
        slip_result = {
            "codigoIDBoleto": f"boleto-sim-{uuid.uuid4().hex[:12]}",
            "valorDesconto": None,
        }
        with patch("bank_slips.gateways.BankSlipGateway.gerar_boleto", return_value=slip_result):
            slip = BankSlipPaymentService().generate_bank_slip_for_fee(fee_requirement=fee, created_by=self._candidate)
        BankSlipPaymentService().simulate_payment(slip)

    def _action_submit_dataset(self, options: Any) -> Any:
        application = self._require_application(options)
        if application.modality != "project":
            raise CommandError("A submissão de dados para auditoria só se aplica a Projetos.")
        from django.core.files.uploadedfile import SimpleUploadedFile

        from audits.services import DatasetAuditService

        if options["channel"] == "file":
            uploaded_file = SimpleUploadedFile(
                "dados-simulados.csv",
                b"coluna_a,coluna_b\n1,2\n",
                content_type="text/csv",
            )
            DatasetAuditService().submit_dataset(
                application=application,
                submitted_by=self._candidate,
                channel="file",
                uploaded_file=uploaded_file,
                note="Dados enviados pela simulação.",
            )
        else:
            DatasetAuditService().submit_dataset(
                application=application,
                submitted_by=self._candidate,
                channel="external_link",
                external_url=options["dataset_url"],
                external_link_declaration=True,
                note="Link externo enviado pela simulação.",
            )
        application.refresh_from_db()
        self._print_event("Dados enviados para auditoria", application)
        return application

    def _action_review(self, options: Any) -> Any:
        from audits.services import DatasetAuditService

        application = self._require_application(options)
        submission = application.audit_submissions.order_by("-submitted_at").first()
        if submission is None:
            raise CommandError("Nenhuma submissão de auditoria para revisar.")
        outcome = options["review"] or "approved"
        DatasetAuditService().review_submission(
            submission=submission,
            reviewer=self._teacher,
            outcome=outcome,
            note="Revisão simulada.",
        )
        application.refresh_from_db()
        self._print_event(f"Auditoria revisada ({outcome})", application)
        return application

    def _action_resolve(self, options: Any) -> Any:
        from audits.services import DatasetAuditService

        application = self._require_application(options)
        submission = application.audit_submissions.order_by("-submitted_at").first()
        if submission is None:
            raise CommandError("Nenhuma submissão de auditoria rejeitada para resolver.")
        resolution = options["resolve"]
        target_term = None
        if resolution == "transfer_term":
            target_term = self._next_term(application.term)
            if options["target_term"] is not None:
                from terms.models import AcademicTerm

                target_term = AcademicTerm.objects.filter(pk=options["target_term"]).first()
            if target_term is None:
                raise CommandError("Informe --target-term ou crie um período posterior.")
        DatasetAuditService().resolve_rejection(
            submission=submission,
            decided_by=self._secretariat,
            resolution=resolution,
            target_term=target_term,
            note="Resolução simulada.",
        )
        application.refresh_from_db()
        self._print_event(f"Rejeição resolvida ({resolution})", application)
        return application

    def _action_schedule_screening(self, options: Any) -> Any:
        from datetime import date, time, timedelta

        from meetings.services import ProjectScreeningService

        application = self._require_application(options)
        # A simulação agenda o evento em uma data passada para que o passo de
        # feedback do docente (que exige o evento já ocorrido) possa rodar.
        ProjectScreeningService().schedule_screening(
            application=application,
            scheduled_by=self._secretariat,
            scheduled_date=date.today() - timedelta(days=1),
            scheduled_time=time(10, 0),
            meeting_mode="online",
            virtual_link="https://meet.example.com/simulacao",
        )
        application.refresh_from_db()
        self._print_event("Triagem agendada", application)
        return application

    def _action_screening_feedback(self, options: Any) -> Any:
        from meetings.services import ProjectScreeningService

        application = self._require_application(options)
        screening = application.project_screening
        if screening is None:
            raise CommandError("A inscrição não possui triagem agendada.")
        feedback = options["screening_feedback"] or "screening_completed"
        ProjectScreeningService().record_feedback(
            screening=screening,
            recorded_by=self._teacher,
            teacher_feedback=feedback,
        )
        application.refresh_from_db()
        self._print_event(f"Feedback do docente registrado ({feedback})", application)
        return application

    def _action_screening_decision(self, options: Any) -> Any:
        from meetings.services import ProjectScreeningService

        application = self._require_application(options)
        screening = application.project_screening
        if screening is None:
            raise CommandError("A inscrição não possui triagem agendada.")
        decision = options["screening_decision"] or "approved_as_project"
        # A decisão final é da secretaria (perfis distintos do feedback docente).
        ProjectScreeningService().record_decision(
            screening=screening,
            decided_by=self._secretariat,
            decision=decision,
            decision_note="Decisão simulada.",
        )
        application.refresh_from_db()
        self._print_event(f"Triagem decidida ({decision})", application)
        return application

    def _action_schedule_consultation(self, options: Any) -> Any:
        from datetime import date, time, timedelta

        from meetings.services import ConsultationMeetingService

        application = self._require_application(options)
        ConsultationMeetingService().schedule_consultation(
            application=application,
            scheduled_by=self._secretariat,
            scheduled_date=date.today() - timedelta(days=1),
            scheduled_time=time(10, 0),
            meeting_mode="online",
            virtual_link="https://meet.example.com/simulacao",
        )
        application.refresh_from_db()
        self._print_event("Reunião de consulta agendada", application)
        return application

    def _action_consultation_feedback(self, options: Any) -> Any:
        from meetings.services import ConsultationMeetingService

        application = self._require_application(options)
        meeting = application.consultation_meeting
        if meeting is None:
            raise CommandError("A inscrição não possui reunião agendada.")
        feedback = options["consultation_feedback"] or "consultation_completed"
        ConsultationMeetingService().record_feedback(
            meeting=meeting,
            recorded_by=self._teacher,
            teacher_feedback=feedback,
        )
        application.refresh_from_db()
        self._print_event(f"Feedback do docente registrado ({feedback})", application)
        return application

    def _action_consultation_decision(self, options: Any) -> Any:
        from meetings.services import ConsultationMeetingService

        application = self._require_application(options)
        meeting = application.consultation_meeting
        if meeting is None:
            raise CommandError("A inscrição não possui reunião agendada.")
        decision = options["consultation_decision"] or "approved_as_consultation"
        # A decisão final é da secretaria (perfis distintos do feedback docente).
        ConsultationMeetingService().record_decision(
            meeting=meeting,
            decided_by=self._secretariat,
            decision=decision,
            decision_note="Decisão simulada.",
        )
        application.refresh_from_db()
        self._print_event(f"Reunião decidida ({decision})", application)
        return application

    def _action_refund(self, options: Any) -> Any:
        from decimal import Decimal

        from payments.services import RefundRequestService

        application = self._require_application(options)
        total_paid = sum(
            (fee.paid_amount for fee in application.fee_requirements.all()),
            Decimal("0.00"),
        )
        if total_paid <= 0:
            raise CommandError("Nenhum valor pago para reembolsar.")
        service = RefundRequestService()
        request = service.create_refund_request(
            application=application,
            requested_by=self._candidate,
            amount=total_paid,
            reason="Reembolso simulado.",
        )
        service.approve(refund_request=request, approved_by=self._secretariat)
        service.execute(refund_request=request, executed_by=self._secretariat)
        application.refresh_from_db()
        self._print_event(f"Reembolso de R$ {total_paid:.2f} executado", application)
        return application

    # ------------------------------------------------------------------
    # Saída
    # ------------------------------------------------------------------

    def _print_event(self, description: str, application: Any) -> None:
        self.stdout.write(self.style.SUCCESS(f"✔ {description}"))

    def _print_status(self, application: Any) -> None:
        from applications.models import ApplicationEvent, ServiceApplication

        protocol = application.protocol
        lifecycle = application.get_lifecycle_status_display()
        modality = application.get_modality_display()
        payment_state = application.payment_state or "—"
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(f"Inscrição {protocol} · {modality}")
        self.stdout.write(f"  lifecycle_status : {application.lifecycle_status} ({lifecycle})")
        self.stdout.write(f"  payment_state    : {payment_state}")
        self.stdout.write(f"  dataset_audit    : {application.dataset_audit_state or '—'}")
        self.stdout.write(f"  term             : {application.term}")

        fees = list(application.fee_requirements.all())
        if fees:
            self.stdout.write("  taxas:")
            for fee in fees:
                paid = "PAGA" if fee.is_paid else "pendente"
                waived = " (dispensada)" if fee.is_waived else ""
                self.stdout.write(f"    - {fee.get_fee_type_display()} R$ {fee.amount} {paid}{waived}")

        instruments = []
        for fee in fees:
            instruments.extend(fee.payment_instruments.all())
        if instruments:
            self.stdout.write("  instrumentos:")
            for instrument in instruments:
                self.stdout.write(
                    f"    - {instrument.get_method_display()} #{instrument.pk} "
                    f"[{instrument.state}] R$ {instrument.amount}"
                )

        screening = getattr(application, "project_screening", None)
        if screening is not None:
            self.stdout.write(
                f"  triagem          : [{screening.state}] "
                f"{screening.get_decision_display() if screening.decision else 'sem decisão'}"
            )
        meeting = getattr(application, "consultation_meeting", None)
        if meeting is not None:
            self.stdout.write(
                f"  reunião          : [{meeting.state}] "
                f"{meeting.get_decision_display() if meeting.decision else 'sem decisão'}"
            )

        submissions = list(application.audit_submissions.all())
        if submissions:
            self.stdout.write("  auditoria:")
            for submission in submissions:
                review = submission.reviews.first()
                outcome = f" · revisão: {review.get_outcome_display()}" if review is not None else ""
                self.stdout.write(
                    f"    - submissão #{submission.pk} "
                    f"[{submission.state}] {submission.get_submission_channel_display()}{outcome}"
                )

        latest_events = list(ApplicationEvent.objects.filter(application=application).order_by("-occurred_at")[:6])
        if latest_events:
            self.stdout.write("  últimos eventos:")
            for event in latest_events:
                self.stdout.write(f"    - {event.occurred_at:%H:%M:%S} {event.event_code}")

        is_terminal = application.lifecycle_status in {
            ServiceApplication.LifecycleStatus.APPROVED_AS_PROJECT,
            ServiceApplication.LifecycleStatus.APPROVED_AS_CONSULTATION,
            ServiceApplication.LifecycleStatus.NOT_APPROVED,
            ServiceApplication.LifecycleStatus.TRANSFERRED,
            ServiceApplication.LifecycleStatus.CANCELED,
        }
        if is_terminal:
            self.stdout.write(self.style.SUCCESS("  → estado terminal alcançado."))
        self.stdout.write("=" * 70)
