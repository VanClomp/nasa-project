"""Testy Szukacza na małych danych syntetycznych.

Uruchomienie z katalogu 4-szukacz:  python -m unittest discover -s tests -v
"""

import base64
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from szukacz import K_FEATURES, load_earth_data, search  # noqa: E402
from szukacz import scoring  # noqa: E402

META_DTYPE = [
    ("id", "<i4"), ("lat", "<f4"), ("lon", "<f4"), ("px_x", "<i4"), ("px_y", "<i4"),
    ("elevation_m", "<f4"), ("nearest_cave_km", "<f4"),
]


def write_dataset(directory, lat, lon, norm, raw=None, cave_km=None):
    """Zapisuje dane Ziemi w formacie z punktu 4.1 specyfikacji (metadane jako .npy)."""
    n = len(lat)
    meta = np.zeros(n, dtype=META_DTYPE)
    meta["id"] = np.arange(n) + 1000
    meta["lat"], meta["lon"] = lat, lon
    meta["px_x"] = np.clip(((np.asarray(lon) + 180) / 360 * 1024).astype(int), 0, 1023)
    meta["px_y"] = np.clip(((90 - np.asarray(lat)) / 180 * 512).astype(int), 0, 511)
    meta["nearest_cave_km"] = 50.0 if cave_km is None else cave_km
    np.save(Path(directory) / "earth_features_norm.npy", np.asarray(norm, dtype=np.float32))
    np.save(
        Path(directory) / "earth_features_raw.npy",
        np.asarray(norm * 100 if raw is None else raw, dtype=np.float32),
    )
    np.save(Path(directory) / "earth_metadata.npy", meta)
    return load_earth_data(directory)


def pair_distances_km(lat, lon):
    xyz = scoring.latlon_to_unit_xyz(lat, lon)
    dist = scoring.great_circle_km(xyz[:, None, :], xyz[None, :, :])
    np.fill_diagonal(dist, np.inf)
    return dist


class RandomWorld(unittest.TestCase):
    """6000 losowych punktów na całej kuli, losowe cechy."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        rng = np.random.default_rng(42)
        cls.n = 6000
        cls.lat = np.degrees(np.arcsin(rng.uniform(-1, 1, cls.n)))
        cls.lon = rng.uniform(-180, 180, cls.n)
        cls.norm = rng.random((cls.n, 12, 9), dtype=np.float32)
        cls.cave = rng.uniform(0, 60, cls.n)
        cls.data = write_dataset(cls.tmp.name, cls.lat, cls.lon, cls.norm, cave_km=cls.cave)
        cls.target = rng.random(9).round(3).tolist()
        cls.weights = rng.random(9).round(3).tolist()
        w = np.asarray(cls.weights, dtype=np.float64)
        diff = np.abs(cls.norm.astype(np.float64) - np.asarray(cls.target))
        cls.expected = 1.0 - (diff * w).sum(axis=2) / w.sum()  # (N, 12) ze wzoru

    @classmethod
    def tearDownClass(cls):
        del cls.data  # zwalnia mmap przed usunięciem katalogu
        cls.tmp.cleanup()

    def test_scores_match_formula(self):
        w = scoring.normalize_weights(self.weights)
        best, month = scoring.score_all(self.data.features_norm, np.float32(self.target), w)
        np.testing.assert_allclose(best, self.expected.max(axis=1), atol=1e-5)
        np.testing.assert_array_equal(month, self.expected.argmax(axis=1))

    def test_without_distance_limit_is_plain_top_k(self):
        result = search(self.data, self.target, self.weights, top_k=100, min_distance_km=0)
        expected_ids = np.argsort(-self.expected.max(axis=1), kind="stable")[:100] + 1000
        self.assertEqual([c["id"] for c in result["candidates"]], expected_ids.tolist())

    def test_distance_limit_keeps_better_point_and_fills_top_k(self):
        limit = 400.0
        result = search(self.data, self.target, self.weights, top_k=100, min_distance_km=limit)
        cands = result["candidates"]
        self.assertEqual(len(cands), 100)
        scores = [c["score"] for c in cands]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual([c["rank"] for c in cands], list(range(1, 101)))

        chosen = np.array([c["id"] for c in cands]) - 1000
        self.assertGreater(pair_distances_km(self.lat[chosen], self.lon[chosen]).min(), limit)

        # Każdy pominięty punkt lepszy od ostatniego zwróconego musi leżeć
        # w zasięgu limitu od zwróconego punktu o wyniku co najmniej tak dobrym.
        best = self.expected.max(axis=1)
        xyz = scoring.latlon_to_unit_xyz(self.lat, self.lon)
        skipped = np.setdiff1d(np.flatnonzero(best > best[chosen[-1]]), chosen)
        self.assertGreater(skipped.size, 0)
        for point in skipped:
            near = scoring.great_circle_km(xyz[chosen], xyz[point]) <= limit
            self.assertTrue((best[chosen][near] >= best[point]).any(), f"punkt {point}")

    def test_selection_matches_simple_greedy_when_pool_has_to_grow(self):
        best = self.expected.max(axis=1).astype(np.float32)
        xyz = self.data.unit_xyz
        for limit, top_k in ((300.0, 20), (2500.0, 20), (6000.0, 20)):
            reference = []
            for point in np.argsort(-best, kind="stable"):
                if len(reference) == top_k:
                    break
                if all(scoring.great_circle_km(xyz[point], xyz[kept]) > limit for kept in reference):
                    reference.append(int(point))
            # Mała pula startowa wymusza kilkukrotne pogłębianie przeszukiwania.
            with mock.patch.object(scoring, "_MIN_POOL", 8), mock.patch.object(scoring, "_POOL_GROWTH", 2):
                small_pool = scoring.select_diverse_top_k(best, xyz, top_k, limit)[:top_k]
            default_pool = scoring.select_diverse_top_k(best, xyz, top_k, limit)
            with self.subTest(limit=limit):
                self.assertEqual(default_pool.tolist(), reference)
                self.assertEqual(small_pool.tolist(), reference)

    def test_require_caves(self):
        result = search(self.data, self.target, self.weights, require_caves=True, cave_max_km=15.0)
        self.assertEqual(len(result["candidates"]), 100)
        self.assertTrue(all(c["nearest_cave_km"] <= 15.0 for c in result["candidates"]))

    def test_response_contract(self):
        result = search(self.data, self.target, self.weights, top_k=20)
        self.assertEqual(
            set(result), {"execution_time_ms", "best_global_month", "heatmap_base64", "candidates"}
        )
        json.dumps(result, allow_nan=False)
        self.assertIn(result["best_global_month"], range(1, 13))
        for cand in result["candidates"]:
            self.assertEqual(
                set(cand),
                {"rank", "id", "lat", "lon", "score", "best_month", "monthly_scores", "features_norm",
                 "features_raw_best_month", "climatogram_12m", "nearest_cave_km"},
            )
            i, month = cand["id"] - 1000, cand["best_month"] - 1
            self.assertEqual(month, int(self.expected[i].argmax()))
            np.testing.assert_allclose(cand["monthly_scores"], self.expected[i], atol=1e-4)
            self.assertAlmostEqual(cand["score"], cand["monthly_scores"][month], places=6)
            self.assertAlmostEqual(cand["lat"], float(self.lat[i]), places=3)
            self.assertAlmostEqual(cand["lon"], float(self.lon[i]), places=3)
            np.testing.assert_allclose(cand["features_norm"], self.norm[i, month], atol=1e-4)
            self.assertEqual(tuple(cand["features_raw_best_month"]), K_FEATURES)
            np.testing.assert_allclose(
                list(cand["features_raw_best_month"].values()), self.norm[i, month] * 100, atol=1e-2
            )
            np.testing.assert_allclose(
                cand["climatogram_12m"]["soil_moisture"], self.norm[i, :, 4] * 100, atol=1e-2
            )

    def test_heatmap_is_rgba_webp_1024x512(self):
        result = search(self.data, self.target, self.weights)
        prefix = "data:image/webp;base64,"
        self.assertTrue(result["heatmap_base64"].startswith(prefix))
        image = Image.open(io.BytesIO(base64.b64decode(result["heatmap_base64"][len(prefix):])))
        self.assertEqual((image.format, image.mode, image.size), ("WEBP", "RGBA", (1024, 512)))
        pixels = np.asarray(image)
        self.assertTrue((pixels[..., :3] == (16, 185, 129)).all())

        best_point = int(self.expected.max(axis=1).argmax())
        x = min(int((self.lon[best_point] + 180) / 360 * 1024), 1023)
        y = min(int((90 - self.lat[best_point]) / 180 * 512), 511)
        self.assertEqual(pixels[y, x, 3], 255)  # najlepszy punkt w pełni kryjący
        self.assertEqual(pixels[..., 3].min(), 0)
        self.assertGreater(len(np.unique(pixels[..., 3])), 50)  # płynna skala krycia
        empty = np.ones(1024 * 512, dtype=bool)
        empty[self.data.pixel_flat] = False
        self.assertTrue((pixels[..., 3].reshape(-1)[empty] == 0).all())  # brak punktów = przezroczyste

    def test_invalid_input(self):
        for kwargs in (
            {"features_norm": self.target[:8]},
            {"weights": self.weights + [1.0]},
            {"weights": [-0.1] + self.weights[1:]},
            {"features_norm": [float("nan")] + self.target[1:]},
            {"top_k": 0},
            {"min_distance_km": -1.0},
        ):
            args = {"features_norm": self.target, "weights": self.weights, **kwargs}
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                search(self.data, **args)

    def test_zero_weights_give_score_one(self):
        result = search(self.data, self.target, [0.0] * 9, top_k=5)
        self.assertEqual([c["score"] for c in result["candidates"]], [1.0] * 5)


class HandBuiltWorld(unittest.TestCase):
    """Kilka punktów o znanym położeniu i wyniku (jedna cecha rządzi rankingiem)."""

    # nazwa: (lat, lon, wartość cechy 0 w najlepszym miesiącu); cel = 1.0
    POINTS = {
        "A_best": (10.0, 20.0, 0.99),
        "A_near_30km": (10.27, 20.0, 0.98),
        "A_near_80km": (10.0, 20.73, 0.97),
        "B_far": (-40.0, 100.0, 0.90),
        "C_far": (60.0, -120.0, 0.80),
        "D_gap": (0.0, -30.0, np.nan),
    }

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        names = list(self.POINTS)
        lat = np.array([self.POINTS[n][0] for n in names])
        lon = np.array([self.POINTS[n][1] for n in names])
        norm = np.zeros((len(names), 12, 9), dtype=np.float32)
        for i, name in enumerate(names):
            norm[i, 6, 0] = self.POINTS[name][2]  # lipiec (indeks 6) najlepszy
        self.data = write_dataset(self.tmp.name, lat, lon, norm)
        self.names = {1000 + i: name for i, name in enumerate(names)}
        self.target = [1.0] + [0.0] * 8
        self.weights = [1.0] + [0.0] * 8

    def tearDown(self):
        del self.data
        self.tmp.cleanup()

    def found(self, **kwargs):
        result = search(self.data, self.target, self.weights, **kwargs)
        return [self.names[c["id"]] for c in result["candidates"]], result

    def test_close_points_collapse_to_the_better_one(self):
        names, result = self.found(top_k=3, min_distance_km=100.0)
        self.assertEqual(names, ["A_best", "B_far", "C_far"])
        self.assertEqual([c["best_month"] for c in result["candidates"]], [7, 7, 7])
        self.assertEqual(result["best_global_month"], 7)
        self.assertAlmostEqual(result["candidates"][0]["score"], 0.99, places=4)

    def test_smaller_limit_lets_the_farther_neighbour_in(self):
        names, _ = self.found(top_k=3, min_distance_km=50.0)
        self.assertEqual(names, ["A_best", "A_near_80km", "B_far"])

    def test_no_limit_returns_neighbours(self):
        names, _ = self.found(top_k=3, min_distance_km=0.0)
        self.assertEqual(names, ["A_best", "A_near_30km", "A_near_80km"])

    def test_fewer_results_when_not_enough_separate_places(self):
        names, result = self.found(top_k=100, min_distance_km=100.0)
        # D_gap ma NaN tylko w lipcu, więc wygrywa innym miesiącem z wynikiem 0.
        self.assertEqual(names, ["A_best", "B_far", "C_far", "D_gap"])
        gap = result["candidates"][3]
        self.assertEqual(gap["score"], 0.0)
        self.assertIsNone(gap["monthly_scores"][6])
        json.dumps(result, allow_nan=False)

    def test_no_candidates(self):
        names, result = self.found(require_caves=True, cave_max_km=1.0)
        self.assertEqual(names, [])
        self.assertIsNone(result["best_global_month"])


class LoadErrors(unittest.TestCase):
    def test_missing_files_and_bad_shapes(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                load_earth_data(tmp)
            lat, lon = np.array([0.0, 1.0]), np.array([0.0, 1.0])
            norm = np.zeros((2, 12, 9), dtype=np.float32)
            write_dataset(tmp, lat, lon, norm)
            np.save(Path(tmp) / "earth_features_raw.npy", np.zeros((3, 12, 9), dtype=np.float32))
            with self.assertRaises(ValueError):
                load_earth_data(tmp)
            np.save(Path(tmp) / "earth_features_raw.npy", norm)
            np.save(Path(tmp) / "earth_metadata.npy", np.zeros(2, dtype=[("id", "<i4"), ("lat", "<f4")]))
            with self.assertRaises(ValueError):
                load_earth_data(tmp)


try:
    from fastapi.testclient import TestClient
except ImportError:  # brak fastapi/httpx w środowisku
    TestClient = None


@unittest.skipIf(TestClient is None, "wymaga pakietów fastapi i httpx")
class HttpApi(unittest.TestCase):
    def test_search_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            rng = np.random.default_rng(7)
            n = 500
            write_dataset(
                tmp,
                np.degrees(np.arcsin(rng.uniform(-1, 1, n))),
                rng.uniform(-180, 180, n),
                rng.random((n, 12, 9), dtype=np.float32),
            )
            os.environ["SZUKACZ_DATA_DIR"] = tmp
            from szukacz.api import app

            body = {"features_norm": [0.5] * 9, "weights": [1.0] * 9, "require_caves": False, "top_k": 10}
            with TestClient(app) as client:
                self.assertEqual(client.get("/health").json()["n_points"], n)
                response = client.post("/search", json=body)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.json()["candidates"]), 10)
                spread = client.post("/search", json={**body, "min_distance_km": 3000})
                self.assertEqual(spread.status_code, 200)
                self.assertEqual(client.post("/search", json={**body, "weights": [1.0] * 8}).status_code, 422)
                self.assertEqual(client.post("/search", json={**body, "top_k": 0}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
