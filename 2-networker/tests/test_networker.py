"""Testy jednostkowe i integracyjne komponentu 2-networker oraz heurystyk mocka."""

from __future__ import annotations

import importlib.util
import py_compile
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "2-networker"))
sys.path.insert(0, str(ROOT_DIR / "3-charakteryzator"))
sys.path.insert(0, str(ROOT_DIR / "4-szukacz"))
sys.path.insert(0, str(ROOT_DIR / "5-precomputer"))

from networker.mock_heuristics import MOCK_BANNER, heuristic_characterize
from networker.regions import resolve_name_hint

HAS_NUMPY_AND_PILLOW = (
    importlib.util.find_spec("numpy") is not None
    and importlib.util.find_spec("PIL") is not None
)


class TestNetworkerComponents(unittest.TestCase):
    def test_all_python_modules_compile_cleanly(self) -> None:
        """Weryfikuje poprawność składniową wszystkich plików .py w repozytorium."""
        for folder in ("2-networker", "3-charakteryzator", "4-szukacz", "5-precomputer"):
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

    def test_heuristic_characterize_contract(self) -> None:
        for body in ("moon", "mars"):
            res = heuristic_characterize(body, lat=-85.2, lon=31.4)
            self.assertEqual(res["target_body"], body)
            self.assertEqual(len(res["features_norm"]), 9)
            self.assertTrue(all(0.0 <= x <= 1.0 for x in res["features_norm"]))
            self.assertEqual(res["_mock_warning"], MOCK_BANNER)
            self.assertIn("nearest_skylight_km", res)
            self.assertEqual(len(res["features_raw"]), 9)

    @unittest.skipUnless(HAS_NUMPY_AND_PILLOW, "Wymaga pakietów numpy oraz pillow (dostępnych w kontenerze)")
    def test_mock_precomputer_integrates_with_szukacz(self) -> None:
        from MOCK_HEURYSTYKA_generate_earth_data import generate_mock_earth_dataset
        from szukacz.data import load_earth_data
        from szukacz.engine import search

        with tempfile.TemporaryDirectory() as tmp:
            generate_mock_earth_dataset(tmp, n_points=500, seed=42)
            marker = Path(tmp) / "UWAGA_DANE_MOCK_HEURYSTYKA.txt"
            self.assertTrue(marker.exists())

            earth = load_earth_data(tmp)
            self.assertEqual(earth.n_points, 500)
            self.assertEqual(earth.n_features, 9)

            profile = heuristic_characterize("moon", -85.2, 31.4)
            result = search(
                earth,
                profile["features_norm"],
                [1.0] * 9,
                top_k=10,
                min_distance_km=100.0,
                require_caves=False,
            )
            self.assertEqual(len(result["candidates"]), 10)
            self.assertTrue(result["heatmap_base64"].startswith("data:image/webp;base64,"))
            for cand in result["candidates"]:
                cand["name_hint"] = resolve_name_hint(cand["lat"], cand["lon"])
                self.assertTrue(len(cand["name_hint"]) > 3)


if __name__ == "__main__":
    unittest.main()
