"""Gera docs/TEST_TRACEABILITY.md a partir de TEST_SCENARIOS.md e dos testes."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "TEST_SCENARIOS.md"
OUT = ROOT / "docs" / "TEST_TRACEABILITY.md"

HEADING_RE = re.compile(r"^## (TS-[A-Z]+-[0-9]{3}) — (.+)$")
TEST_RE = re.compile(r"^\s*def (test_TS_[A-Z]+_[0-9]{3}[A-Za-z0-9_]*)\(")

scenarios: list[tuple[str, str]] = []
for line in DOC.read_text(encoding="utf-8").splitlines():
    match = HEADING_RE.match(line)
    if match:
        scenarios.append((match.group(1), match.group(2).strip()))

tests: dict[str, list[str]] = {}
for path in sorted(ROOT.glob("apps/**/test*.py")):
    relative = path.relative_to(ROOT)
    for line in path.read_text(encoding="utf-8").splitlines():
        match = TEST_RE.match(line)
        if not match:
            continue
        test_name = match.group(1)
        id_match = re.match(r"test_(TS_[A-Z]+_[0-9]{3})", test_name)
        if not id_match:
            continue
        scenario_id = id_match.group(1).replace("_", "-")
        tests.setdefault(scenario_id, []).append(f"`{relative}::{test_name}`")

lines = [
    "# Matriz de rastreabilidade — cenários × testes",
    "",
    "Gerada a partir de `docs/TEST_SCENARIOS.md` e dos arquivos `apps/**/test*.py`.",
    "Atualize-a com `python scripts/gen_test_traceability.py` (ou manualmente) ao mover/renomear testes.",
    "",
    "| ID | Cenário | Arquivo::teste | Status |",
    "|---|---|---|---|",
]
for scenario_id, title in scenarios:
    entries = tests.get(scenario_id, [])
    test_cell = "<br>".join(entries) if entries else "—"
    status = "Coberto" if entries else "Sem teste"
    lines.append(f"| {scenario_id} | {title} | {test_cell} | {status} |")

unknown = sorted(set(tests) - {scenario_id for scenario_id, _ in scenarios})
if unknown:
    lines.extend(["", "## IDs usados em testes sem cenário no documento", ""])
    for scenario_id in unknown:
        lines.append(f"- {scenario_id}: " + ", ".join(tests[scenario_id]))

OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Gerado {OUT} com {len(scenarios)} cenários e {len(tests)} IDs cobertos.")
