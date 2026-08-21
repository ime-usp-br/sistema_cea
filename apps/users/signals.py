from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User

_RBAC_GROUPS = frozenset(choice.value for choice in User.Role)


@receiver(post_save, sender=User)
def keep_rbac_group_in_sync(sender, instance, **kwargs):
    """Mantém a assinatura de grupo RBAC alinhada ao campo ``role``.

    O campo ``role`` é a fonte da verdade para menus, views e permissões do
    sistema. Os grupos de autorização (candidate/teacher/secretariat/
    administrator) são derivados dele: qualquer mudança de perfil é refletida
    nos grupos automaticamente, independentemente do ponto de entrada (admin,
    shell, serviços, factories).
    """
    if instance.role not in _RBAC_GROUPS:
        return

    current = set(
        instance.groups.filter(name__in=_RBAC_GROUPS).values_list("name", flat=True)
    )
    desired = {instance.role}
    if current == desired:
        return

    to_add = list(Group.objects.filter(name__in=desired - current))
    to_remove = list(Group.objects.filter(name__in=current - desired))
    if to_add:
        instance.groups.add(*to_add)
    if to_remove:
        instance.groups.remove(*to_remove)
