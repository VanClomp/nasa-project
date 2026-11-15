"""Testy jednostkowe komponentu 2-networker."""

from __future__ import annotations

import py_compile
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "2-networker"))

from networker.regions import resolve_name_hint


class TestNetworkerComponents(unittest.TestCase):
    def test_all_python_modules_compile_cleanly(self) -> None:
        """Weryfikuje poprawność składniową wszystkich plików .py w repozytorium."""
        for folder in ("2-networker", "3-charakteryzator", "4-szukacz"):
            for py_file in (ROOT_DIR / folder).rglob("*.py"):
                py_compile.compile(str(py_file), doraise=True)

    def test_resolve_name_hint_known_analogs(self) -> None:
        self.assertIn("McMurdo", resolve_name_hint(-77.55, 161.80))
        self.assertIn("Atacama", resolve_name_hint(-24.08, -69.92))
        self.assertIn("Mauna Loa", resolve_name_hint(19.47, -155.59))
        self.assertIn("Devon Island", resolve_name_hint(75.38, -89.68))

    def test_resolve_name_hint_fallback_zones(self) -> None:
        hint = resolve_name_hint(-80.0, 10.0)
        self.assertIn("Antarktyczna", hint)


if __name__ == "__main__":
    unittest.main()
