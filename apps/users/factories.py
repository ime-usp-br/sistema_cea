import uuid

import factory

from base.factories import fake_br

from .models import User


def _unique_tax_id() -> str:
    """Gera um CPF/CNPJ Faker que ainda não existe no banco (coluna unique)."""
    while True:
        tax_id = fake_br.cpf()
        if not User.objects.filter(tax_id=tax_id).exists():
            return tax_id


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.LazyFunction(lambda: uuid.uuid4().hex[:24])
    email = factory.LazyAttribute(
        lambda o: f"candidato{uuid.uuid4().hex[:16]}@example.com"
    )
    password = factory.PostGenerationMethodCall("set_password", "senha-aleatoria-123")
    full_name = factory.LazyFunction(fake_br.name)
    tax_id = factory.LazyFunction(_unique_tax_id)
    role = User.Role.CANDIDATE
    is_email_verified = True
    is_active = True


class TeacherFactory(UserFactory):
    role = User.Role.TEACHER


class SecretariatFactory(UserFactory):
    role = User.Role.SECRETARIAT


class AdministratorFactory(UserFactory):
    role = User.Role.ADMINISTRATOR
