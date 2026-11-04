"""Meta-testes de rastreabilidade dos cenários (T2.4)."""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

DOC_SCENARIO_RE = re.compile(r"TS-[A-Z]+-\d{3}")
TEST_NAME_RE = re.compile(r"def (test_TS_[A-Z]+_\d{3}[A-Za-z0-9_]*)\(")
TEST_ID_RE = re.compile(r"test_(TS_[A-Z]+_\d{3})")


class TestTraceabilityTests(SimpleTestCase):
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
