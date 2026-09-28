from django.db import migrations

TEMPLATE = {
    "code": "email_verification",
    "name": "Confirmação de e-mail (cadastro)",
    "description": "Link de confirmação do cadastro de candidato externo (D8).",
    "audience": "candidate",
    "subject": "Confirme seu e-mail — Inscrições CEA",
    "body": (
        "Olá, {{ candidate_name }}!\n\n"
        "Confirme seu e-mail para ativar sua conta no sistema de Inscrições CEA:\n"
        "{{ verification_url }}\n\n"
        "Se você não solicitou este cadastro, ignore esta mensagem.\n\n"
        "Atenciosamente,\nEquipe CEA — IME/USP"
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
        ("notifications", "0006_seed_meeting_decision_templates"),
    ]

    operations = [
        migrations.RunPython(seed_template, unseed_template),
    ]
