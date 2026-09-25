from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.base import Model as DjangoModel

from notifications.models import NotificationTemplate
from terms.models import AcademicTerm

from .models import User

# Grupo virtual que concede à Secretaria o acesso restrito ao admin (paridade
# com o legado, onde a equipe opera semestres e modelos de e-mail).
SECRETARIAT_ADMIN_GROUP = "Secretaria (admin restrito)"

SECRETARIAT_MODEL_ACTIONS: dict[type[DjangoModel], tuple[str, ...]] = {
    AcademicTerm: ("view", "add", "change"),
    NotificationTemplate: ("view", "change"),
}


def ensure_secretariat_admin_permissions() -> dict[str, list[str]]:
    """Sincroniza (idempotente) permissões de admin para Secretaria/Admin.

    - Garante ``is_staff=True`` para toda a Secretaria e Administradores;
    - Cria/atualiza o grupo *Secretaria (admin restrito)* com permissões
      limitadas a ``academic_terms`` (view/add/change) e
      ``notification_templates`` (view/change);
    - Associa todos os usuários com papel ``secretariat`` ao grupo.

    Retorna um resumo para diagnóstico (listas de codenames e usuários).
    """
    group, _ = Group.objects.get_or_create(name=SECRETARIAT_ADMIN_GROUP)

    permissions: list[Permission] = []
    applied: list[str] = []
    for model, actions in SECRETARIAT_MODEL_ACTIONS.items():
        content_type = ContentType.objects.get_for_model(model)
        for action in actions:
            codename = f"{action}_{model._meta.model_name}"
            perm = Permission.objects.filter(
                content_type=content_type, codename=codename
            ).first()
            if perm is None:
                continue
            permissions.append(perm)
            applied.append(codename)
    group.permissions.set(permissions)

    staff_users = User.objects.filter(
        role__in=[User.Role.SECRETARIAT, User.Role.ADMINISTRATOR]
    )
    staff_users.update(is_staff=True)

    for user in User.objects.filter(role=User.Role.SECRETARIAT):
        user.groups.add(group)

    return {"codenames": applied}
