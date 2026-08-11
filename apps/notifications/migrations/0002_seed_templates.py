from django.db import migrations

CANONICAL_TEMPLATES = [
    {
        "code": "account_created",
        "name": "Conta criada",
        "description": "Boas-vindas e confirmação de conta.",
        "audience": "candidate",
        "subject": "Bem-vindo(a) ao Inscrições CEA, {{ candidate_name }}",
        "body": (
            "Olá, {{ candidate_name }}!\n\n"
            "Sua conta no sistema de Inscrições CEA foi criada com sucesso. "
            "A partir de agora você pode submeter inscrições e acompanhar o andamento.\n\n"
            "Atenciosamente,\nEquipe CEA — IME/USP"
        ),
    },
    {
        "code": "application_submitted_candidate",
        "name": "Inscrição submetida (candidato)",
        "description": "Confirmação de submissão para o candidato.",
        "audience": "candidate",
        "subject": "Inscrição {{ protocol }} submetida com sucesso",
        "body": (
            "Olá, {{ candidate_name }}!\n\n"
            "Sua inscrição {{ protocol }} ({{ modality }}) foi submetida com sucesso "
            "no período {{ term }}.\n\n"
            "Guarde este protocolo para acompanhar o andamento da sua solicitação.\n\n"
            "Atenciosamente,\nEquipe CEA — IME/USP"
        ),
    },
    {
        "code": "application_submitted_center",
        "name": "Inscrição submetida (equipe CEA)",
        "description": "Aviso interno de nova inscrição para a equipe.",
        "audience": "center",
        "subject": "Nova inscrição {{ protocol }} ({{ modality }})",
        "body": (
            "Nova inscrição recebida:\n\n"
            "Protocolo: {{ protocol }}\n"
            "Candidato(a): {{ candidate_name }}\n"
            "Modalidade: {{ modality }}\n"
            "Período: {{ term }}\n\n"
            "Equipe CEA — IME/USP"
        ),
    },
    {
        "code": "dataset_correction_requested",
        "name": "Correção de dados solicitada",
        "description": "Notifica o candidato que precisa corrigir os dados.",
        "audience": "candidate",
        "subject": "Correção solicitada para a inscrição {{ protocol }}",
        "body": (
            "Olá, {{ candidate_name }}!\n\n"
            "Os dados da sua inscrição {{ protocol }} precisam de correção:\n\n"
            "{{ note }}\n\n"
            "Acesse o sistema para atualizar as informações e reenviar.\n\n"
            "Atenciosamente,\nEquipe CEA — IME/USP"
        ),
    },
    {
        "code": "dataset_approved",
        "name": "Auditoria aprovada",
        "description": "Notifica o candidato sobre aprovação da auditoria.",
        "audience": "candidate",
        "subject": "Dados aprovados — inscrição {{ protocol }}",
        "body": (
            "Olá, {{ candidate_name }}!\n\n"
            "A auditoria dos dados da sua inscrição {{ protocol }} foi aprovada. "
            "O próximo passo é a realização do pagamento da taxa.\n\n"
            "Atenciosamente,\nEquipe CEA — IME/USP"
        ),
    },
    {
        "code": "dataset_rejected",
        "name": "Auditoria rejeitada (candidato)",
        "description": "Notifica o candidato sobre rejeição da auditoria.",
        "audience": "candidate",
        "subject": "Dados rejeitados — inscrição {{ protocol }}",
        "body": (
            "Olá, {{ candidate_name }}!\n\n"
            "A auditoria dos dados da sua inscrição {{ protocol }} foi rejeitada:\n\n"
            "{{ note }}\n\n"
            "A equipe CEA fará contato para as próximas providências.\n\n"
            "Atenciosamente,\nEquipe CEA — IME/USP"
        ),
    },
    {
        "code": "dataset_rejected_secretariat",
        "name": "Auditoria rejeitada (secretaria)",
        "description": "Aviso interno sobre rejeição aguardando decisão.",
        "audience": "center",
        "subject": "Rejeição de dados — inscrição {{ protocol }}",
        "body": (
            "Os dados da inscrição {{ protocol }} ({{ modality }}) foram rejeitados "
            "pelo docente e aguardam decisão da secretaria.\n\n"
            "Candidato(a): {{ candidate_name }}\n\n"
            "Equipe CEA — IME/USP"
        ),
    },
    {
        "code": "payment_created",
        "name": "Cobrança criada",
        "description": "Notifica o candidato sobre Pix ou boleto disponível.",
        "audience": "candidate",
        "subject": "Pagamento disponível — inscrição {{ protocol }}",
        "body": (
            "Olá, {{ candidate_name }}!\n\n"
            "Foi gerada uma cobrança no valor de R$ {{ amount }} ({{ method }}) "
            "para a inscrição {{ protocol }}.\n\n"
            "Acesse o sistema para concluir o pagamento.\n\n"
            "Atenciosamente,\nEquipe CEA — IME/USP"
        ),
    },
    {
        "code": "payment_confirmed",
        "name": "Pagamento confirmado",
        "description": "Notifica o candidato sobre pagamento confirmado.",
        "audience": "candidate",
        "subject": "Pagamento confirmado — inscrição {{ protocol }}",
        "body": (
            "Olá, {{ candidate_name }}!\n\n"
            "O pagamento no valor de R$ {{ amount }} ({{ method }}) da inscrição "
            "{{ protocol }} foi confirmado.\n\n"
            "Atenciosamente,\nEquipe CEA — IME/USP"
        ),
    },
    {
        "code": "screening_scheduled",
        "name": "Triagem agendada",
        "description": "Notifica o candidato sobre o agendamento da triagem.",
        "audience": "candidate",
        "subject": "Triagem agendada — inscrição {{ protocol }}",
        "body": (
            "Olá, {{ candidate_name }}!\n\n"
            "A triagem da sua inscrição {{ protocol }} foi agendada para "
            "{{ scheduled_date }} às {{ scheduled_time }} ({{ meeting_mode }}).\n\n"
            "{% if virtual_link %}Link: {{ virtual_link }}\n{% endif %}"
            "{% if place %}Local: {{ place }}\n{% endif %}\n"
            "Atenciosamente,\nEquipe CEA — IME/USP"
        ),
    },
]


def seed_templates(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    for item in CANONICAL_TEMPLATES:
        NotificationTemplate.objects.update_or_create(
            code=item["code"],
            defaults={
                "name": item["name"],
                "description": item["description"],
                "audience": item["audience"],
                "subject": item["subject"],
                "body": item["body"],
                "is_active": True,
            },
        )


def unseed_templates(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    NotificationTemplate.objects.filter(
        code__in={item["code"] for item in CANONICAL_TEMPLATES}
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_templates, unseed_templates),
    ]
