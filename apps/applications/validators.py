import re

from django.core.exceptions import ValidationError

PHONE_SEPARATOR_RE = re.compile(r"\s*(?:[,;/]|\s+e\s+)\s*", re.IGNORECASE)
PERSON_NAME_RE = re.compile(
    r"^[^\W\d_](?:[^\W\d_]|[ .'’\-])*$",
    re.UNICODE,
)


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


def _normalize_phone_digits(value: str) -> str:
    """Remove a máscara e o prefixo internacional (+55), quando presentes."""
    digits = _strip_digits(value)
    if len(digits) in (12, 13) and digits.startswith("55"):
        digits = digits[2:]
    return digits


def _validate_phone_number(value: str) -> str:
    digits = _normalize_phone_digits(value)
    if len(digits) not in (10, 11):
        raise ValidationError("Informe um telefone com DDD (10 ou 11 dígitos).")
    ddd = int(digits[:2])
    if not 11 <= ddd <= 99:
        raise ValidationError("Informe um DDD válido (11 a 99).")
    if len(digits) == 11 and digits[2] != "9":
        raise ValidationError("Informe um celular válido (9 dígitos iniciados por 9).")
    return digits


def validate_contact_phone(value: str, *, require_whatsapp: bool = False) -> str:
    """Valida uma lista de telefones (DDD + 8 ou 9 dígitos).

    Aceita vários números separados por vírgula, ponto e vírgula, barra ou
    " e ". Devolve os números normalizados (somente dígitos), separados por
    vírgula, para armazenamento consistente.
    """
    raw = (value or "").strip()
    if not raw:
        raise ValidationError("Informe ao menos um telefone para contato.")
    parts = [part.strip() for part in PHONE_SEPARATOR_RE.split(raw) if part.strip()]
    if not parts:
        raise ValidationError("Informe ao menos um telefone para contato.")

    normalized: list[str] = []
    for part in parts:
        try:
            normalized.append(_validate_phone_number(part))
        except ValidationError as exc:
            raise ValidationError(
                f"Telefone inválido: {part}. {exc.messages[0]}"
            ) from exc

    if require_whatsapp and not any(
        len(number) == 11 and number[2] == "9" for number in normalized
    ):
        raise ValidationError(
            "Informe um número de celular com WhatsApp (DDD + 9 dígitos, iniciado por 9)."
        )
    return ", ".join(normalized)


def validate_person_name(
    value: str,
    *,
    label: str = "nome",
    require_full_name: bool = False,
) -> str:
    """Valida nomes de pessoas: sem números e sem símbolos estranhos."""
    cleaned = " ".join((value or "").split())
    if not cleaned:
        return cleaned
    if any(char.isdigit() for char in cleaned) or not PERSON_NAME_RE.match(cleaned):
        raise ValidationError(
            f"Informe um {label} válido, sem números ou símbolos."
        )
    if require_full_name and len(cleaned.split()) < 2:
        raise ValidationError(f"Informe o {label} completo.")
    return cleaned


def validate_digits(
    value: str,
    *,
    label: str,
    min_length: int = 1,
    max_length: int = 20,
) -> str:
    """Valida campos puramente numéricos (agência, conta etc.).

    Aceita separadores usuais (espaço, ponto e hífen do dígito verificador),
    mas rejeita letras e símbolos estranhos; devolve somente os dígitos.
    """
    if re.search(r"[^\d.\-\s]", value or ""):
        raise ValidationError(f"Informe apenas números no {label}.")
    digits = _strip_digits(value)
    if not digits:
        raise ValidationError(f"Informe o {label}.")
    if len(digits) < min_length or len(digits) > max_length:
        raise ValidationError(
            f"Informe um {label} válido ({min_length} a {max_length} dígitos)."
        )
    return digits
