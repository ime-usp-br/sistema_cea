from django.db import migrations

TEMPLATE = {
    "code": "bank_slip_generation_failure",
    "name": "Falha na geração de boleto (equipe CEA)",
    "description": "Alerta a equipe sobre indisponibilidade do serviço SOAP de boletos.",
    "audience": "center",
    "subject": "Falha na geração de boleto — inscrição {{ protocol }}",
    "body": (
        "A geração do boleto da inscrição {{ protocol }} ({{ modality }}) falhou "
        "por indisponibilidade do serviço de boletos.\n\n"
        "Candidato(a): {{ candidate_name }}\n"
        "Período: {{ term }}\n\n"
        "Erro: {{ error_message }}\n\n"
        "Providencie a emissão manual e/ou verifique a disponibilidade do gateway.\n\n"
        "Equipe CEA — IME/USP"
    ),
}


def seed_template(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    NotificationTemplate.objects.update_or_create(
        code=TEMPLATE["code"],
        defaults={
            "name": TEMPLATE["name"],
            "description": TEMPLATE["description"],
            "audience": TEMPLATE["audience"],
            "subject": TEMPLATE["subject"],
            "body": TEMPLATE["body"],
            "is_active": True,
        },
    )


def unseed_template(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    NotificationTemplate.objects.filter(code=TEMPLATE["code"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0002_seed_templates"),
    ]

    operations = [
        migrations.RunPython(seed_template, unseed_template),
    ]
