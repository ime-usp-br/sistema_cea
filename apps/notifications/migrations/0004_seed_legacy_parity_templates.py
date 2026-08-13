from django.db import migrations

CANONICAL_TEMPLATES = [
    {
        "code": "service_modality_changed",
        "name": "Modalidade do serviço alterada",
        "description": "Notifica o candidato quando a secretaria altera a modalidade da inscrição.",
        "audience": "candidate",
        "subject": "Sua inscrição {{ protocol }} foi alterada para {{ new_modality }}",
        "body": (
            "Olá, {{ candidate_name }}!\n\n"
            "A modalidade da sua inscrição {{ protocol }} foi alterada pela secretaria "
            "para {{ new_modality }}. Isso pode gerar uma nova cobrança.\n\n"
            "Acesse o sistema para visualizar o novo boleto/Pix e acompanhar o andamento.\n\n"
            "Atenciosamente,\nEquipe CEA — IME/USP"
        ),
    },
    {
        "code": "payment_failure_regenerated",
        "name": "Boleto vencido regenerado automaticamente",
        "description": "Informa o candidato que um boleto vencido foi reemitido automaticamente.",
        "audience": "candidate",
        "subject": "Novo boleto disponível — inscrição {{ protocol }}",
        "body": (
            "Olá, {{ candidate_name }}!\n\n"
            "O boleto da sua inscrição {{ protocol }} venceu. Para não interromper o "
            "processo, geramos um novo boleto com nova data de vencimento.\n\n"
            "Acesse o sistema para baixar o novo boleto e realizar o pagamento.\n\n"
            "Atenciosamente,\nEquipe CEA — IME/USP"
        ),
    },
    {
        "code": "payment_slip_regenerated",
        "name": "Boleto reemitido pela secretaria",
        "description": "Notifica o candidato sobre boleto reemitido manualmente pela secretaria.",
        "audience": "candidate",
        "subject": "Novo boleto emitido — inscrição {{ protocol }}",
        "body": (
            "Olá, {{ candidate_name }}!\n\n"
            "A secretaria reemitiu o boleto da sua inscrição {{ protocol }} com uma nova "
            "data de vencimento.\n\n"
            "Acesse o sistema para baixar o novo boleto e realizar o pagamento.\n\n"
            "Atenciosamente,\nEquipe CEA — IME/USP"
        ),
    },
    {
        "code": "overdue_payment_reminder",
        "name": "Cobrança de boleto vencido",
        "description": "Cobra o candidato por boleto vencido não pago.",
        "audience": "candidate",
        "subject": "Seu boleto venceu — inscrição {{ protocol }}",
        "body": (
            "Olá, {{ candidate_name }}!\n\n"
            "Identificamos que o boleto da sua inscrição {{ protocol }} venceu e ainda "
            "não foi pago.\n\n"
            "Acesse o sistema para gerar uma nova via do boleto e regularizar sua situação.\n\n"
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
        ("notifications", "0003_seed_bank_slip_failure_template"),
    ]

    operations = [
        migrations.RunPython(seed_templates, unseed_templates),
    ]
