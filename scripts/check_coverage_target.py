"""Mostra a cobertura real de produção e a distância até a meta de 92%.

A meta é um aviso até ser atingida; o script nunca falha por cobertura para não
bloquear merges enquanto a dívida é reduzida (decisão registrada no plano).
"""

from __future__ import annotations

import os
from pathlib import Path

import coverage

TARGET = 92.0


def main() -> None:
    data_file = os.environ.get("COVERAGE_FILE", "/tmp/.coverage")
    if not Path(data_file).exists():
        print(f"Sem dados de cobertura em {data_file}; nada a reportar.")
        return
    cov = coverage.Coverage(data_file=data_file)
    cov.load()
    with open(os.devnull, "w", encoding="utf-8") as sink:
        total = cov.report(file=sink, show_missing=False)
    print(f"Cobertura de produção: {total:.2f}% (meta: {TARGET:.0f}%).")
    if total < TARGET:
        print(
            f"Aviso: faltam {TARGET - total:.2f} p.p. para a meta. "
            "Não bloqueia o merge, conforme decisão do plano."
        )
    else:
        print("Meta de cobertura atingida.")


if __name__ == "__main__":
    main()
