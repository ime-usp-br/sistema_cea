"""Seeder dos grupos de autorização (RBAC) do sistema.

Cria os quatro grupos previstos em ARCHITECTURE.md §7 (candidate, teacher,
secretariat, administrator) e atribui as permissões de model correspondentes a
cada papel. É um data migration, portanto roda em qualquer ambiente (dev, staging
e produção) via `migrate`, garantindo que os grupos existam onde a aplicação for
deployada — não apenas no desenvolvimento.

O controle de acesso por objeto (ex.: candidato vê apenas as próprias inscrições)
é aplicado nas views/querysets, independentemente das permissões de model aqui.
"""

from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations


# Ações padronizadas do Django por model.
_ADD = "add"
_CHANGE = "change"
_DELETE = "delete"
_VIEW = "view"
_ALL_ACTIONS = (_ADD, _CHANGE, _DELETE, _VIEW)

# (app_label, model_name) de todos os models do sistema.
_MODELS = {
    "applications": [
        "catalogoption",
        "serviceapplication",
        "applicationcatalogselection",
        "applicationattachment",
        "applicationevent",
    ],
    "audits": [
        "datasetauditsubmission",
        "datasetauditreview",
        "datasetauditresolution",
    ],
    "bank_slips": ["bankslippaymentinstrument"],
    "files": ["fileasset"],
    "imports": ["legacyownershipclaim"],
    "meetings": ["projectscreening", "consultationmeeting"],
    "notifications": ["notificationtemplate", "notificationdispatch"],
    "payments": [
        "feerequirement",
        "paymentinstrument",
        "manualpaymentconfirmation",
        "refundrequest",
    ],
    "pix": ["pixpaymentinstrument", "pixwebhookevent"],
    "terms": ["academicterm"],
    "users": ["user", "identityproviderlink"],
}


def _codename(action, model_name):
    return f"{action}_{model_name}"


def _perm(perms, app_label, model_name, actions):
    for action in actions:
        perms.add((app_label, _codename(action, model_name)))


def _all_perms_for_apps(perms, app_labels):
    for app_label in app_labels:
        for model_name in _MODELS.get(app_label, []):
            _perm(perms, app_label, model_name, _ALL_ACTIONS)


def _build_role_permissions() -> dict[str, set[tuple[str, str]]]:
    """Retorna {nome_do_grupo: set de permissões (app_label, codename)}."""

    administrator: set[tuple[str, str]] = set()
    _all_perms_for_apps(administrator, _MODELS.keys())

    secretariat: set[tuple[str, str]] = set()
    internal_apps = [
        "applications",
        "audits",
        "bank_slips",
        "files",
        "imports",
        "meetings",
        "notifications",
        "payments",
        "pix",
        "terms",
    ]
    _all_perms_for_apps(secretariat, internal_apps)
    # Secretaria apenas visualiza usuários (gestão de papéis é do administrador).
    _perm(secretariat, "users", "user", (_VIEW,))

    teacher: set[tuple[str, str]] = set()
    for model_name in _MODELS["applications"]:
        _perm(teacher, "applications", model_name, (_VIEW,))
    _perm(teacher, "audits", "datasetauditsubmission", (_VIEW,))
    _perm(teacher, "audits", "datasetauditreview", (_ADD, _CHANGE, _VIEW))
    _perm(teacher, "audits", "datasetauditresolution", (_ADD, _CHANGE, _VIEW))
    _perm(teacher, "meetings", "projectscreening", (_ADD, _CHANGE, _VIEW))
    _perm(teacher, "meetings", "consultationmeeting", (_ADD, _CHANGE, _VIEW))
    _perm(teacher, "notifications", "notificationtemplate", (_VIEW,))
    _perm(teacher, "notifications", "notificationdispatch", (_VIEW,))
    _perm(teacher, "files", "fileasset", (_VIEW,))

    candidate: set[tuple[str, str]] = set()
    _perm(candidate, "applications", "serviceapplication", (_ADD,))
    _perm(candidate, "applications", "applicationcatalogselection", (_ADD,))
    _perm(candidate, "applications", "applicationattachment", (_ADD,))
    _perm(candidate, "applications", "applicationevent", (_ADD, _VIEW))
    _perm(candidate, "audits", "datasetauditsubmission", (_ADD, _VIEW))
    _perm(candidate, "terms", "academicterm", (_VIEW,))
    _perm(candidate, "files", "fileasset", (_VIEW,))
    _perm(candidate, "payments", "paymentinstrument", (_VIEW,))
    _perm(candidate, "pix", "pixpaymentinstrument", (_VIEW,))
    _perm(candidate, "bank_slips", "bankslippaymentinstrument", (_VIEW,))

    return {
        "administrator": administrator,
        "secretariat": secretariat,
        "teacher": teacher,
        "candidate": candidate,
    }


def create_groups(apps, schema_editor):
    # Garante que todas as permissões de model existam antes de referenciá-las.
    for app_config in global_apps.get_app_configs():
        if app_config.models_module is not None:
            create_permissions(app_config, apps=global_apps, verbosity=0)

    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")

    role_permissions = _build_role_permissions()
    qs = Permission.objects.filter(
        content_type__app_label__in={app for app, _ in set().union(*role_permissions.values())}
    )
    permissions_by_key = {(p.content_type.app_label, p.codename): p for p in qs}

    for group_name, perm_keys in role_permissions.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        group.permissions.set(
            [permissions_by_key[key] for key in perm_keys if key in permissions_by_key]
        )


def remove_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(
        name__in={"administrator", "secretariat", "teacher", "candidate"}
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0003_user_role"),
    ]

    operations = [
        migrations.RunPython(create_groups, remove_groups),
    ]
