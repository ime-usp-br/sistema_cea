from django.db import migrations

NEW_BODY = (
    "Olá, {{ candidate_name }}!\n\n"
    "Sua inscrição {{ protocol }} ({{ modality }}) foi submetida com sucesso "
    "no período {{ term }}.\n\n"
    "Guarde este protocolo para acompanhar o andamento da sua solicitação.\n\n"
    "{% if boleto_failed %}"
    "⚠️ Atenção: enfrentamos uma instabilidade momentânea na geração do seu "
    "boleto bancário. Ele será emitido e enviado em instantes; caso não o "
    "receba, acesse o sistema para gerar uma nova via.\n\n"
    "{% endif %}"
    "Atenciosamente,\nEquipe CEA — IME/USP"
)


def update_template(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    NotificationTemplate.objects.filter(
        code="application_submitted_candidate"
    ).update(body=NEW_BODY)


def revert_template(apps, schema_editor):
    # Sem estado anterior confiável, reverter para o corpo canônico sem o aviso.
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    NotificationTemplate.objects.filter(code="application_submitted_candidate").update(
        body=(
            "Olá, {{ candidate_name }}!\n\n"
            "Sua inscrição {{ protocol }} ({{ modality }}) foi submetida com sucesso "
            "no período {{ term }}.\n\n"
            "Guarde este protocolo para acompanhar o andamento da sua solicitação.\n\n"
            "Atenciosamente,\nEquipe CEA — IME/USP"
        )
    )


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0004_seed_legacy_parity_templates"),
    ]

    operations = [
        migrations.RunPython(update_template, revert_template),
    ]
