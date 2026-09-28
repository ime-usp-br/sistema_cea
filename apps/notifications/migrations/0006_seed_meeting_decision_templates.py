from django.db import migrations

CANONICAL_TEMPLATES = [
    {
        "code": "screening_decision",
        "name": "Decisão da triagem",
        "description": "Informa o candidato sobre a decisão da triagem.",
        "audience": "candidate",
        "subject": "Resultado da triagem — inscrição {{ protocol }}",
        "body": (
            "Olá, {{ candidate_name }}!\n\n"
            "A triagem da sua inscrição {{ protocol }} foi concluída.\n\n"
            "Resultado: {{ decision }}\n"
            "{% if decision_note %}Observações: {{ decision_note }}\n{% endif %}\n"
            "{{ next_step }}\n\n"
            "Atenciosamente,\nEquipe CEA — IME/USP"
        ),
    },
    {
        "code": "consultation_scheduled",
        "name": "Reunião de consulta agendada",
        "description": "Informa o candidato sobre o agendamento da reunião de consulta.",
        "audience": "candidate",
        "subject": "Reunião de consulta agendada — inscrição {{ protocol }}",
        "body": (
            "Olá, {{ candidate_name }}!\n\n"
            "A reunião de consulta da sua inscrição {{ protocol }} foi agendada para "
            "{{ scheduled_date }} às {{ scheduled_time }} ({{ meeting_mode }}).\n\n"
            "{% if virtual_link %}Link: {{ virtual_link }}\n{% endif %}"
            "{% if place %}Local: {{ place }}\n{% endif %}\n"
            "Atenciosamente,\nEquipe CEA — IME/USP"
        ),
    },
    {
        "code": "consultation_decision",
        "name": "Decisão da reunião de consulta",
        "description": "Informa o candidato sobre a decisão da reunião de consulta.",
        "audience": "candidate",
        "subject": "Resultado da reunião de consulta — inscrição {{ protocol }}",
        "body": (
            "Olá, {{ candidate_name }}!\n\n"
            "A reunião de consulta da sua inscrição {{ protocol }} foi concluída.\n\n"
            "Resultado: {{ decision }}\n"
            "{% if decision_note %}Observações: {{ decision_note }}\n{% endif %}\n"
            "{{ next_step }}\n\n"
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
        ("notifications", "0005_seed_submission_boleto_failed_template"),
    ]

    operations = [
        migrations.RunPython(seed_templates, unseed_templates),
    ]
