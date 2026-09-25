from django.db import migrations


def sync_secretariat_admin_permissions(apps, schema_editor) -> None:
    User = apps.get_model("users", "User")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    group, _ = Group.objects.get_or_create(name="Secretaria (admin restrito)")

    targets = {
        ("terms", "academicterm"): ("view", "add", "change"),
        ("notifications", "notificationtemplate"): ("view", "change"),
    }
    permissions = []
    for (app_label, model_name), actions in targets.items():
        try:
            content_type = ContentType.objects.get(
                app_label=app_label, model=model_name
            )
        except ContentType.DoesNotExist:
            continue
        for action in actions:
            perm = Permission.objects.filter(
                content_type=content_type,
                codename=f"{action}_{model_name}",
            ).first()
            if perm is not None:
                permissions.append(perm)
    group.permissions.set(permissions)

    User.objects.filter(
        role__in=["secretariat", "administrator"]
    ).update(is_staff=True)

    for user in User.objects.filter(role="secretariat"):
        user.groups.add(group)


def noop(apps, schema_editor) -> None:
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0004_seed_groups"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(
            sync_secretariat_admin_permissions,
            reverse_code=noop,
        ),
    ]
