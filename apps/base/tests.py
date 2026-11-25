"""Meta-testes de rastreabilidade dos cenários (T2.4)."""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

DOC_SCENARIO_RE = re.compile(r"TS-[A-Z]+-\d{3}")
TEST_NAME_RE = re.compile(r"def (test_TS_[A-Z]+_\d{3}[A-Za-z0-9_]*)\(")
TEST_ID_RE = re.compile(r"test_(TS_[A-Z]+_\d{3})")
TEST_FUNC_RE = re.compile(r"^(\s*)(?:async\s+)?def (test_[A-Za-z0-9_]+)\(")
TS_STRICT_RE = re.compile(r"^test_TS_[A-Z]+_\d{3}")
TST_STRICT_RE = re.compile(r"^test_TST_[A-Z]+_\d{3}")
TST_ID_RE = re.compile(r"\bTST-[A-Z]+-\d{3}\b")
TST_COMMENT_RE = re.compile(r"#\s*TST-[A-Z]+-\d{3}")
TS_NAME_CAPTURE_RE = re.compile(r"test_(TS_[A-Z]+_\d{3})")
TST_NAME_CAPTURE_RE = re.compile(r"test_(TST_[A-Z]+_\d{3})")
COBRE_RE = re.compile(r"^\s*#\s*Cobre:\s*(.+)$")
INVENTORY_ROW_RE = re.compile(r"^\| (TST-[A-Z]+-\d{3}) \|", re.MULTILINE)



class TestTraceabilityTests(SimpleTestCase):
    # TST-BASE-010
    def test_ids_de_cenarios_citados_existem_no_documento(self) -> None:
        base_dir = Path(settings.BASE_DIR)
        scenarios_doc = (base_dir / "docs" / "TEST_SCENARIOS.md").read_text(
            encoding="utf-8"
        )
        documented = set(DOC_SCENARIO_RE.findall(scenarios_doc))

        missing: dict[str, list[str]] = {}
        for test_file in sorted(base_dir.glob("apps/**/test*.py")):
            relative = test_file.relative_to(base_dir)
            for line in test_file.read_text(encoding="utf-8").splitlines():
                name_match = TEST_NAME_RE.search(line)
                if name_match is None:
                    continue
                id_match = TEST_ID_RE.match(name_match.group(1))
                if id_match is None:
                    continue
                scenario_id = id_match.group(1).replace("_", "-")
                if scenario_id not in documented:
                    missing.setdefault(scenario_id, []).append(
                        f"{relative}::{name_match.group(1)}"
                    )

        self.assertEqual(
            missing,
            {},
            "Testes citam IDs ausentes em docs/TEST_SCENARIOS.md: "
            + ", ".join(
                f"{scenario_id} ({', '.join(tests)})"
                for scenario_id, tests in sorted(missing.items())
            ),
        )

    # TST-BASE-011
    def test_todos_os_testes_tem_id_ts_ou_tst(self) -> None:
        base_dir = Path(settings.BASE_DIR)
        documented = set(
            DOC_SCENARIO_RE.findall(
                (base_dir / "docs" / "TEST_SCENARIOS.md").read_text(encoding="utf-8")
            )
        )
        inventory = self._inventory_ids(base_dir)
        errors: list[str] = []
        seen_tst: dict[str, str] = {}

        for test_file in sorted(base_dir.glob("apps/**/test*.py")):
            relative = test_file.relative_to(base_dir)
            lines = test_file.read_text(encoding="utf-8").splitlines()
            for index, line in enumerate(lines):
                match = TEST_FUNC_RE.match(line)
                if match is None:
                    continue
                name = match.group(2)
                if TS_STRICT_RE.match(name):
                    id_match = TS_NAME_CAPTURE_RE.match(name)
                    assert id_match is not None
                    scenario_id = id_match.group(1).replace("_", "-")
                    if scenario_id not in documented:
                        errors.append(f"{relative}::{name} cita {scenario_id} ausente")
                    continue
                if name.startswith("test_TS_"):
                    errors.append(f"{relative}::{name} fora do padrão test_TS_<ÁREA>_<3 dígitos>")
                    continue
                tst_id = self._tst_id_for(name, lines, index)
                if tst_id is None:
                    errors.append(f"{relative}::{name} sem TS-* ou TST-*")
                    continue
                if tst_id in seen_tst:
                    errors.append(
                        f"{tst_id} duplicado em {relative}::{name} e {seen_tst[tst_id]}"
                    )
                seen_tst[tst_id] = f"{relative}::{name}"
                if tst_id not in inventory:
                    errors.append(f"{relative}::{name} usa {tst_id} fora do inventário")

        for test_file in sorted((base_dir / "e2e").glob("test_*.py")):
            relative = test_file.relative_to(base_dir)
            lines = test_file.read_text(encoding="utf-8").splitlines()
            for index, line in enumerate(lines):
                match = TEST_FUNC_RE.match(line)
                if match is None:
                    continue
                marker = self._marker_for(lines, index)
                if marker is None:
                    errors.append(f"{relative}::{match.group(2)} sem # Cobre")
                    continue
                ids = re.findall(r"(?:TS|TST)-[A-Z]+-\d{3}", marker)
                if not ids:
                    errors.append(f"{relative}::{match.group(2)} com # Cobre sem ID")
                for identifier in ids:
                    if identifier.startswith("TS-") and identifier not in documented:
                        errors.append(f"{relative}::{match.group(2)} cita {identifier} ausente")
                    if identifier.startswith("TST-") and identifier not in inventory:
                        errors.append(f"{relative}::{match.group(2)} cita {identifier} fora do inventário")

        self.assertEqual(errors, [], "\n".join(errors))

    # TST-BASE-012
    def test_inventario_tst_esta_atualizado(self) -> None:
        base_dir = Path(settings.BASE_DIR)
        inventory = self._inventory_ids(base_dir)
        code_ids: set[str] = set()

        for test_file in sorted(base_dir.glob("apps/**/test*.py")):
            lines = test_file.read_text(encoding="utf-8").splitlines()
            for index, line in enumerate(lines):
                match = TEST_FUNC_RE.match(line)
                if match is None:
                    continue
                name = match.group(2)
                if TS_STRICT_RE.match(name):
                    continue
                tst_id = self._tst_id_for(name, lines, index)
                if tst_id is not None:
                    code_ids.add(tst_id)

        for test_file in sorted((base_dir / "e2e").glob("test_*.py")):
            lines = test_file.read_text(encoding="utf-8").splitlines()
            for index, line in enumerate(lines):
                match = TEST_FUNC_RE.match(line)
                if match is None:
                    continue
                marker = self._marker_for(lines, index)
                if marker is not None:
                    code_ids.update(TST_ID_RE.findall(marker))

        self.assertEqual(
            code_ids,
            inventory,
            "docs/TEST_INVENTORY.md está desatualizado; rode scripts/gen_test_inventory.py",
        )

    def _inventory_ids(self, base_dir: Path) -> set[str]:
        content = (base_dir / "docs" / "TEST_INVENTORY.md").read_text(encoding="utf-8")
        return set(INVENTORY_ROW_RE.findall(content))

    def _tst_id_for(self, name: str, lines: list[str], index: int) -> str | None:
        if TST_STRICT_RE.match(name):
            id_match = TST_NAME_CAPTURE_RE.match(name)
            assert id_match is not None
            return id_match.group(1).replace("_", "-")
        for previous in reversed(lines[max(0, index - 3) : index]):
            match = TST_ID_RE.search(previous)
            if match is not None:
                return match.group(0)
        return None

    def _marker_for(self, lines: list[str], index: int) -> str | None:
        for previous in reversed(lines[max(0, index - 6) : index]):
            match = COBRE_RE.match(previous)
            if match is not None:
                return match.group(1)
        return None
