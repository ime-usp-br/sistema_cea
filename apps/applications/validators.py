import re

from django.core.exceptions import ValidationError


def _strip_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _cpf_check_digits(body: str) -> str:
    def calculate(section: str, start: int) -> int:
        total = sum(int(digit) * (start - index) for index, digit in enumerate(section))
        remainder = total % 11
        return 0 if remainder < 2 else 11 - remainder

    first = calculate(body, 10)
    second = calculate(body + str(first), 11)
    return f"{first}{second}"


def _cnpj_check_digits(body: str) -> str:
    weights_first = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    weights_second = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    def calculate(section: str, weights: list[int]) -> int:
        total = sum(int(digit) * weight for digit, weight in zip(section, weights, strict=True))
        remainder = total % 11
        return 0 if remainder < 2 else 11 - remainder

    first = calculate(body, weights_first)
    second = calculate(body + str(first), weights_second)
    return f"{first}{second}"


def validate_br_tax_id(value: str) -> str:
    """Valida CPF ou CNPJ e retorna apenas os dígitos (sem máscara)."""
    digits = _strip_digits(value)
    if len(digits) == 11:
        if len(set(digits)) == 1 or _cpf_check_digits(digits[:9]) != digits[9:]:
            raise ValidationError("CPF inválido.")
        return digits
    if len(digits) == 14:
        if len(set(digits)) == 1 or _cnpj_check_digits(digits[:12]) != digits[12:]:
            raise ValidationError("CNPJ inválido.")
        return digits
    raise ValidationError("Informe um CPF ou CNPJ válido.")
