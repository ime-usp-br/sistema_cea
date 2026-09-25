from __future__ import annotations

from typing import Any

from .models import AcademicTerm


def resolve_term(request: Any) -> AcademicTerm | None:
    """Resolve o semestre selecionado na requisição.

    Lê ``?term=`` (novo) e o legado ``?semester_id=``; quando ausente, cai no
    :meth:`AcademicTerm.current`. Usado pelas listas da Secretaria para que o
    filtro de semestre tenha default no semestre atual.
    """
    raw = request.GET.get("term") or request.GET.get("semester_id")
    if raw:
        term = AcademicTerm.objects.filter(pk=raw).first()
        if term is not None:
            return term
    return AcademicTerm.current()


def term_filter_id(request: Any) -> str | None:
    """Devolve o id bruto enviado em ``?term=``/``?semester_id=`` (para o form)."""
    raw = request.GET.get("term") or request.GET.get("semester_id")
    return str(raw) if raw else None
