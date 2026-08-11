from django.db import migrations

CANONICAL_OPTIONS = [
    ("institutional_tie", "student", "Estudante"),
    ("institutional_tie", "staff", "Funcionário"),
    ("institutional_tie", "faculty", "Professor"),
    ("institutional_tie", "other", "Outro"),
    ("project_purpose", "undergraduate_research", "Iniciação Científica"),
    ("project_purpose", "master", "Mestrado"),
    ("project_purpose", "doctorate", "Doutorado"),
    ("project_purpose", "livre_docencia", "Livre Docência"),
    ("project_purpose", "publication", "Publicação"),
    ("project_purpose", "other", "Outra"),
    ("knowledge_area", "technological", "Tecnológica"),
    ("knowledge_area", "health_biological", "Médica ou Biológica"),
    ("knowledge_area", "social_human", "Social ou Humana"),
    ("knowledge_area", "economic", "Econômica"),
    ("knowledge_area", "other", "Outra"),
    ("funding_agency", "fapesp", "FAPESP"),
    ("funding_agency", "finep", "FINEP"),
    ("funding_agency", "cnpq", "CNPq"),
    ("funding_agency", "other", "Outra"),
]


def seed_catalog_options(apps, schema_editor):
    CatalogOption = apps.get_model("applications", "CatalogOption")
    for category, code, label in CANONICAL_OPTIONS:
        CatalogOption.objects.update_or_create(
            category=category,
            code=code,
            defaults={"label": label, "is_active": True},
        )


def unseed_catalog_options(apps, schema_editor):
    CatalogOption = apps.get_model("applications", "CatalogOption")
    CatalogOption.objects.filter(
        category__in={category for category, _, _ in CANONICAL_OPTIONS}
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("applications", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(seed_catalog_options, unseed_catalog_options),
    ]
