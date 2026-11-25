"""Gera docs/TEST_INVENTORY.md a partir dos IDs TST-* da suíte.

Testes de cenário continuam rastreados por TS-* em TEST_SCENARIOS.md.
Testes de infraestrutura/complementares usam TST-* no nome ou em um comentário
imediatamente anterior à função. O script falha se algum teste unitário não
tiver nem TS-* nem TST-*, ou se um ID TST-* for duplicado.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "TEST_INVENTORY.md"

TEST_FUNC_RE = re.compile(r"^(\s*)(?:async\s+)?def (test_[A-Za-z0-9_]+)\(")
TS_STRICT_RE = re.compile(r"^test_TS_[A-Z]+_\d{3}")
TST_NAME_RE = re.compile(r"^(test_TST_[A-Z]+_\d{3})")
TST_RE = re.compile(r"\b(TST-[A-Z]+-\d{3})\b")
COBRE_RE = re.compile(r"^\s*#\s*Cobre:\s*(.+)$")


def _unit_rows() -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    errors: list[str] = []
    seen: dict[str, str] = {}

    for path in sorted((ROOT / "apps").rglob("test*.py")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            match = TEST_FUNC_RE.match(line)
            if match is None:
                continue
            name = match.group(2)
            relative = str(path.relative_to(ROOT))
            if TS_STRICT_RE.match(name):
                continue
            tst_id: str | None = None
            name_match = TST_NAME_RE.match(name)
            if name_match is not None:
                tst_id = name_match.group(1).replace("test_", "", 1).replace("_", "-", 1)
                tst_id = tst_id.replace("_", "-")
            else:
                for previous in reversed(lines[max(0, index - 3) : index]):
                    comment = TST_RE.search(previous)
                    if comment is not None:
                        tst_id = comment.group(1)
                        break
            if tst_id is None:
                errors.append(f"{relative}::{name} sem TS-* ou TST-*")
                continue
            if tst_id in seen:
                errors.append(
                    f"{tst_id} duplicado em {relative}::{name} e {seen[tst_id]}"
                )
                continue
            seen[tst_id] = f"{relative}::{name}"
            rows.append((tst_id, relative, name))

    if errors:
        print("\n".join(errors), file=sys.stderr)
        raise SystemExit(1)
    return rows


def _e2e_rows() -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for path in sorted((ROOT / "e2e").glob("test_*.py")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            match = TEST_FUNC_RE.match(line)
            if match is None:
                continue
            name = match.group(2)
            relative = str(path.relative_to(ROOT))
            marker = next(
                (
                    cobre.group(1)
                    for cobre in (
                        COBRE_RE.match(previous)
                        for previous in reversed(lines[max(0, index - 6) : index])
                    )
                    if cobre is not None
                ),
                None,
            )
            if marker is None:
                continue
            for tst_id in TST_RE.findall(marker):
                rows.append((tst_id, relative, name))
    return rows


def main() -> None:
    rows = _unit_rows() + _e2e_rows()
    seen: set[str] = set()
    for tst_id, _, _ in rows:
        if tst_id in seen:
            raise SystemExit(f"ID TST duplicado: {tst_id}")
        seen.add(tst_id)

    table = [
        "# Inventário de testes de infraestrutura (TST)",
        "",
        "Gerado por `scripts/gen_test_inventory.py`. Testes de cenário usam `TS-*`",
        "em `TEST_SCENARIOS.md`; testes de infraestrutura/complementares usam `TST-*`.",
        "",
        "| ID | Arquivo | Teste |",
        "|---|---|---|",
    ]
    for tst_id, file, name in sorted(rows):
        table.append(f"| {tst_id} | `{file}` | `{name}` |")
    table.append("")
    OUT.write_text("\n".join(table), encoding="utf-8")
    print(f"{len(rows)} IDs TST-* gravados em {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
