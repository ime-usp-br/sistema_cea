from faker import Faker
from faker.config import AVAILABLE_LOCALES

# Semente fixa para reprodutibilidade em CI: mesma semente => mesma "massa".
# Cada chamada avança a sequência, então os registros diferem entre si,
# mas a suíte inteira é determinística dado o seed.
Faker.seed(1234)

# pt_BR fornece CPF/CNPJ e telefones válidos de verdade.
fake_br = Faker("pt_BR")
fake_en = Faker("en_GB")


def _unique_username(faker: Faker, index: int) -> str:
    """Gera um username curto, válido e único (Django limita a 150 chars)."""
    return f"{faker.user_name()[:90]}_{index}"


__all__ = ["fake_br", "fake_en", "_unique_username", "AVAILABLE_LOCALES"]
