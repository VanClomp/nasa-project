"""Szukacz tests on small synthetic data.

Run from the 4-szukacz folder:  python -m unittest discover -s tests -v
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

from szukacz import K_FEATURES, error_map_detail, load_earth_data, search  # noqa: E402
from szukacz import maps, scoring  # noqa: E402

META_DTYPE = [
    ("id", "<i4"), ("lat", "<f4"), ("lon", "<f4"), ("px_x", "<i4"), ("px_y", "<i4"),
    ("elevation_m", "<f4"), ("nearest_cave_km", "<f4"),
]


def heatmap_pixels(lat, lon):
    """Pixel of the 1024x512 grid that contains the point: (px_x, px_y)."""
    px_x = np.clip(((np.asarray(lon) + 180) / 360 * 1024).astype(int), 0, 1023)
    px_y = np.clip(((90 - np.asarray(lat)) / 180 * 512).astype(int), 0, 511)
    return px_x, px_y


def write_dataset(directory, lat, lon, norm, raw=None, cave_km=None):
    """Writes Earth data in the format of spec section 4.1 (metadata as .npy)."""
    n = len(lat)
    meta = np.zeros(n, dtype=META_DTYPE)
    meta["id"] = np.arange(n) + 1000
    meta["lat"], meta["lon"] = lat, lon
    meta["px_x"], meta["px_y"] = heatmap_pixels(lat, lon)
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


def decode_error_map(data_uri):
    """Error-map image (palette PNG) as an (H, W, 4) RGBA array."""
    prefix = "data:image/png;base64,"
    assert data_uri.startswith(prefix), data_uri[:40]
    image = Image.open(io.BytesIO(base64.b64decode(data_uri[len(prefix):])))
    assert image.format == "PNG", image.format
    return np.asarray(image.convert("RGBA"))


def one_feature_dataset(directory, lat, lon, error):
    """Points with a given error: only feature 0 counts, target = 1.0, all months equal."""
    norm = np.zeros((len(lat), 12, 9), dtype=np.float32)
    norm[:, :, 0] = (1.0 - np.asarray(error))[:, None]
    return write_dataset(directory, np.asarray(lat), np.asarray(lon), norm)


ONE_FEATURE = {"features_norm": [1.0] + [0.0] * 8, "weights": [1.0] + [0.0] * 8}


def reference_detail(detail, lat, lon, error, center_lon):
    """Reference detailed map computed directly: every pixel checks every point.

    A pixel gets the error of the point nearest to its centre (|dlon| + |dlat|), as long as
    that point is no farther than detail.reach_deg in each axis. Returns (expected
    grid, mask of unambiguous pixels). Ambiguous are the pixels lying
    closer than about one pixel to the border between two points or to the border
    of the reach: there the result depends on rounding the point position to a pixel.
    """
    height, width = detail.errors.shape
    half_lon, half_lat = (detail.lon_max - detail.lon_min) / 2, (detail.lat_max - detail.lat_min) / 2
    deg_x, deg_y = 2 * half_lon / width, 2 * half_lat / height
    pixel_lon = detail.lon_min + (np.arange(width) + 0.5) * deg_x
    pixel_lat = detail.lat_max - (np.arange(height) + 0.5) * deg_y
    # Point longitudes in a continuous range around the window centre (wrapping at the 180th meridian).
    lon = center_lon + (np.asarray(lon) - center_lon + 180.0) % 360.0 - 180.0
    # A point farther than 2 * reach_deg changes no pixel, and reach_deg
    # is at most a quarter of the window's half; a band of 0.8 half around the window takes them with margin.
    close = (
        (np.abs(lon - center_lon) <= 1.8 * half_lon)
        & (lat >= detail.lat_min - 0.8 * half_lat)
        & (lat <= detail.lat_max + 0.8 * half_lat)
    )
    lat, lon, error = np.asarray(lat)[close], lon[close], np.asarray(error)[close]

    expected = np.full((height, width), np.nan)
    clear = np.zeros((height, width), dtype=bool)
    columns = np.arange(width)
    dx = np.abs(pixel_lon[:, None] - lon[None, :])  # (W, P)
    for row in range(height):
        dy = np.abs(pixel_lat[row] - lat)  # (P,)
        dist = dx + dy[None, :]
        nearest = dist.argmin(axis=1)
        first = dist[columns, nearest]
        dist[columns, nearest] = np.inf
        second = dist.min(axis=1)
        near_x, near_y = dx[columns, nearest], dy[nearest]
        filled = (near_x <= detail.reach_deg) & (near_y <= detail.reach_deg)
        expected[row, filled] = error[nearest[filled]]
        clear[row] = (
            (second - first > 1.2 * (deg_x + deg_y))
            & (np.abs(near_x - detail.reach_deg) > 0.75 * deg_x)
            & (np.abs(near_y - detail.reach_deg) > 0.75 * deg_y)
        )
    return expected, clear


class RandomWorld(unittest.TestCase):
    """6000 random points over the whole sphere, random features."""

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
        del cls.data  # releases the mmap before the folder is deleted
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

        # Every skipped point better than the last returned one must lie
        # within the limit of a returned point with a score at least as good.
        best = self.expected.max(axis=1)
        xyz = scoring.latlon_to_unit_xyz(self.lat, self.lon)
        skipped = np.setdiff1d(np.flatnonzero(best > best[chosen[-1]]), chosen)
        self.assertGreater(skipped.size, 0)
        for point in skipped:
            near = scoring.great_circle_km(xyz[chosen], xyz[point]) <= limit
            self.assertTrue((best[chosen][near] >= best[point]).any(), f"point {point}")

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
            # A small starting pool forces the search to go deeper several times.
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
            set(result),
            {"execution_time_ms", "best_global_month", "heatmap_base64", "error_map", "candidates"},
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
        self.assertEqual(pixels[y, x, 3], 255)  # best point fully opaque
        self.assertEqual(pixels[..., 3].min(), 0)
        self.assertGreater(len(np.unique(pixels[..., 3])), 50)  # smooth opacity scale
        empty = np.ones(1024 * 512, dtype=bool)
        empty[self.data.pixel_flat] = False
        self.assertTrue((pixels[..., 3].reshape(-1)[empty] == 0).all())  # no points = transparent

    def test_error_map_covers_whole_earth(self):
        result = search(self.data, self.target, self.weights)
        error_map = result["error_map"]
        self.assertEqual(set(error_map), {"image_base64", "width", "height", "bounds", "scale", "stats"})
        self.assertEqual((error_map["width"], error_map["height"]), (1024, 512))
        self.assertEqual(
            error_map["bounds"], {"lat_min": -90.0, "lat_max": 90.0, "lon_min": -180.0, "lon_max": 180.0}
        )
        self.assertEqual(error_map["scale"], {"min": 0.0, "max": 0.5, "colors": list(maps.ERROR_COLORS)})

        # Reference from the formula: point error = 1 - match in the best month,
        # a pixel takes the smallest error of its points.
        point_error = 1.0 - self.expected.max(axis=1)
        px_x, px_y = heatmap_pixels(self.lat, self.lon)
        expected_grid = np.full(512 * 1024, np.inf)
        np.minimum.at(expected_grid, px_y * 1024 + px_x, point_error)
        expected_grid[np.isinf(expected_grid)] = np.nan
        best, _ = scoring.score_all(
            self.data.features_norm, np.float32(self.target), scoring.normalize_weights(self.weights)
        )
        grid = maps.global_error_grid(self.data, best)
        self.assertEqual(grid.shape, (512, 1024))
        np.testing.assert_allclose(grid, expected_grid.reshape(512, 1024), atol=1e-5)
        self.assertEqual(int(np.isfinite(grid).sum()), self.data.pixel_flat.size)

        pixels = decode_error_map(error_map["image_base64"])
        self.assertEqual(pixels.shape, (512, 1024, 4))
        np.testing.assert_array_equal(pixels, maps.colorize_error(grid, 0.5))
        np.testing.assert_array_equal(pixels[..., 3] == 255, np.isfinite(grid))  # data = fully opaque

        stats = error_map["stats"]
        self.assertEqual(stats["n_points"], self.n)
        self.assertAlmostEqual(stats["min"], point_error.min(), delta=1e-4)
        self.assertAlmostEqual(stats["mean"], point_error.mean(), delta=1e-4)
        self.assertAlmostEqual(stats["max"], point_error.max(), delta=1e-4)

    def test_error_map_scale_is_fixed_and_adjustable(self):
        # The same scale for every query; changing error_scale_max only changes the colours.
        narrow = search(self.data, self.target, self.weights, error_scale_max=0.25)["error_map"]
        self.assertEqual(narrow["scale"]["max"], 0.25)
        best, _ = scoring.score_all(
            self.data.features_norm, np.float32(self.target), scoring.normalize_weights(self.weights)
        )
        np.testing.assert_array_equal(
            decode_error_map(narrow["image_base64"]),
            maps.colorize_error(maps.global_error_grid(self.data, best), 0.25),
        )

    def test_detail_map_matches_direct_computation(self):
        target, weights = np.float32(self.target), scoring.normalize_weights(self.weights)
        point_error = 1.0 - self.expected.max(axis=1)
        # (lat, lon, radius): middle of a continent, window across the 180th meridian, high latitude.
        for lat, lon, radius_km in ((20.0, 30.0, 1500.0), (-60.0, 179.0, 1500.0), (75.0, -100.0, 1000.0)):
            with self.subTest(lat=lat, lon=lon):
                detail = maps.detail_error_grid(self.data, target, weights, lat, lon, radius_km, 192)
                self.assertEqual(detail.errors.shape, (192, 192))
                expected, clear = reference_detail(detail, self.lat, self.lon, point_error, lon)
                np.testing.assert_allclose(detail.errors[clear], expected[clear], atol=1e-5)
                # The test must cover most of the map, including pixels with and without data.
                self.assertGreater(clear.mean(), 0.6)
                self.assertGreater(int(np.isfinite(expected[clear]).sum()), 5000)
                self.assertGreater(int(np.isnan(expected[clear]).sum()), 100)

                dlon = (self.lon - lon + 180.0) % 360.0 - 180.0 + lon
                inside = (
                    (dlon >= detail.lon_min) & (dlon < detail.lon_max)
                    & (self.lat > detail.lat_min) & (self.lat <= detail.lat_max)
                )
                np.testing.assert_allclose(np.sort(detail.point_errors), np.sort(point_error[inside]), atol=1e-5)

    def test_detail_map_window(self):
        detail = maps.detail_error_grid(
            self.data, np.float32(self.target), scoring.normalize_weights(self.weights), 60.0, 10.0, 500.0, 128
        )
        half_lat = 500.0 / 111.195  # the window is a square in km: 500 km in every direction
        self.assertAlmostEqual(detail.lat_min, 60.0 - half_lat, places=3)
        self.assertAlmostEqual(detail.lat_max, 60.0 + half_lat, places=3)
        self.assertAlmostEqual(detail.lon_min, 10.0 - 2.0 * half_lat, places=3)  # cos(60) = 0.5
        self.assertAlmostEqual(detail.lon_max, 10.0 + 2.0 * half_lat, places=3)

    def test_invalid_input(self):
        for kwargs in (
            {"features_norm": self.target[:8]},
            {"weights": self.weights + [1.0]},
            {"weights": [-0.1] + self.weights[1:]},
            {"features_norm": [float("nan")] + self.target[1:]},
            {"top_k": 0},
            {"min_distance_km": -1.0},
            {"error_scale_max": 0.0},
        ):
            args = {"features_norm": self.target, "weights": self.weights, **kwargs}
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                search(self.data, **args)

    def test_invalid_detail_input(self):
        for kwargs in (
            {"lat": 90.5},
            {"lat": float("nan")},
            {"lon": float("inf")},
            {"radius_km": 0.5},
            {"radius_km": 2500.0},
            {"size_px": 32},
            {"size_px": 2048},
            {"size_px": 100.5},
            {"features_norm": self.target[:8]},
            {"weights": [-0.1] + self.weights[1:]},
            {"error_scale_max": float("nan")},
        ):
            args = {"features_norm": self.target, "weights": self.weights, "lat": 10.0, "lon": 20.0, **kwargs}
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                error_map_detail(self.data, **args)

    def test_zero_weights_give_score_one(self):
        result = search(self.data, self.target, [0.0] * 9, top_k=5)
        self.assertEqual([c["score"] for c in result["candidates"]], [1.0] * 5)


class HandBuiltWorld(unittest.TestCase):
    """A few points with known positions and scores (one feature decides the ranking)."""

    # name: (lat, lon, value of feature 0 in the best month); target = 1.0
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
            norm[i, 6, 0] = self.POINTS[name][2]  # July (index 6) is best
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
        # D_gap has NaN only in July, so it wins with another month with score 0.
        self.assertEqual(names, ["A_best", "B_far", "C_far", "D_gap"])
        gap = result["candidates"][3]
        self.assertEqual(gap["score"], 0.0)
        self.assertIsNone(gap["monthly_scores"][6])
        json.dumps(result, allow_nan=False)

    def test_no_candidates(self):
        names, result = self.found(require_caves=True, cave_max_km=1.0)
        self.assertEqual(names, [])
        self.assertIsNone(result["best_global_month"])
        # The cave filter does not apply to the maps: the error is computed for all points.
        self.assertEqual(result["error_map"]["stats"]["n_points"], len(self.POINTS))

    def test_detail_around_lonely_point(self):
        # D_gap: no data in July, feature 0 = 0 in the other months, i.e. error 1.0.
        result = error_map_detail(self.data, self.target, self.weights, 0.0, -30.0, radius_km=100.0, size_px=64)
        json.dumps(result, allow_nan=False)
        self.assertEqual(result["error_map"]["stats"], {"n_points": 1, "min": 1.0, "mean": 1.0, "max": 1.0})
        pixels = decode_error_map(result["error_map"]["image_base64"])
        self.assertEqual(pixels.shape, (64, 64, 4))
        # Error above the end of the scale: the last colour (#FFE5D9), fully opaque.
        self.assertEqual(tuple(pixels[32, 32]), (0xFF, 0xE5, 0xD9, 255))
        # A single point does not flood the map: it fills at most 1/8 of its width in each direction.
        filled = pixels[..., 3] == 255
        self.assertTrue(filled[26:38, 26:38].all())
        self.assertFalse(filled[:22].any() or filled[42:].any() or filled[:, :22].any() or filled[:, 42:].any())

    def test_detail_without_data(self):
        result = error_map_detail(self.data, self.target, self.weights, 45.0, 0.0, radius_km=100.0, size_px=64)
        json.dumps(result, allow_nan=False)
        self.assertEqual(
            result["error_map"]["stats"], {"n_points": 0, "min": None, "mean": None, "max": None}
        )
        pixels = decode_error_map(result["error_map"]["image_base64"])
        self.assertEqual(pixels.shape, (64, 64, 4))
        self.assertEqual(int(pixels[..., 3].max()), 0)


class LatticeWorld(unittest.TestCase):
    """A regular grid of points every 0.25 degree with a 3x3 hole (land with a lake).

    The grid cell is smaller than a global-map pixel (about 0.35 degree),
    so the global map merges neighbouring points, and the detailed map should not.
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        lat, lon = np.meshgrid(9.0 + 0.25 * np.arange(9), 19.0 + 0.25 * np.arange(9), indexing="ij")
        hole = (np.abs(lat - 10.0) < 0.3) & (np.abs(lon - 20.5) < 0.3)
        cls.lat, cls.lon = lat[~hole], lon[~hole]
        cls.error = 0.05 + 0.005 * np.arange(cls.lat.size)  # every point has a different error
        cls.data = one_feature_dataset(cls.tmp.name, cls.lat, cls.lon, cls.error)
        cls.detail = maps.detail_error_grid(
            cls.data, np.float32(ONE_FEATURE["features_norm"]),
            scoring.normalize_weights(ONE_FEATURE["weights"]), 10.0, 20.0, 150.0, 256,
        )

    @classmethod
    def tearDownClass(cls):
        del cls.data
        cls.tmp.cleanup()

    def pixel(self, lat, lon):
        d = self.detail
        height, width = d.errors.shape
        return (
            int((d.lat_max - lat) / (d.lat_max - d.lat_min) * height),
            int((lon - d.lon_min) / (d.lon_max - d.lon_min) * width),
        )

    def test_reach_follows_point_spacing(self):
        self.assertEqual(self.lat.size, 72)
        self.assertAlmostEqual(self.detail.reach_deg, 0.75 * 0.25, places=4)

    def test_every_point_is_shown_separately(self):
        for lat, lon, error in zip(self.lat, self.lon, self.error):
            self.assertAlmostEqual(float(self.detail.errors[self.pixel(lat, lon)]), error, places=5)
        shown = np.unique(np.round(self.detail.errors[np.isfinite(self.detail.errors)], 5))
        np.testing.assert_allclose(shown, self.error, atol=1e-5)

        # On the global map the same points take fewer pixels than there are points.
        best, _ = scoring.score_all(
            self.data.features_norm, np.float32(ONE_FEATURE["features_norm"]),
            scoring.normalize_weights(ONE_FEATURE["weights"]),
        )
        coarse = maps.global_error_grid(self.data, best)
        self.assertLess(int(np.isfinite(coarse).sum()), 60)

    def test_matches_direct_computation(self):
        expected, clear = reference_detail(self.detail, self.lat, self.lon, self.error, 20.0)
        np.testing.assert_allclose(self.detail.errors[clear], expected[clear], atol=1e-5)
        self.assertGreater(clear.mean(), 0.75)

    def test_gaps_stay_empty(self):
        errors = self.detail.errors
        self.assertTrue(np.isnan(errors[self.pixel(10.0, 20.5)]))  # middle of the lake
        self.assertTrue(np.isnan(errors[self.pixel(8.7, 18.7)]))  # off the land
        self.assertTrue(np.isnan(errors[0]).all() and np.isnan(errors[:, 0]).all())
        # The cell of an edge point ends just past half a cell (0.75 instead of 0.5 cell).
        self.assertAlmostEqual(float(errors[self.pixel(8.85, 20.0)]), float(errors[self.pixel(9.0, 20.0)]))
        self.assertTrue(np.isnan(errors[self.pixel(8.78, 20.0)]))

    def test_response(self):
        result = error_map_detail(self.data, **ONE_FEATURE, lat=10.0, lon=20.0, radius_km=150.0, size_px=256)
        json.dumps(result, allow_nan=False)
        self.assertEqual(set(result), {"execution_time_ms", "center", "radius_km", "km_per_px", "error_map"})
        self.assertEqual(result["center"], {"lat": 10.0, "lon": 20.0})
        self.assertEqual(result["radius_km"], 150.0)
        self.assertAlmostEqual(result["km_per_px"], 300.0 / 256, places=4)

        error_map = result["error_map"]
        self.assertEqual(set(error_map), {"image_base64", "width", "height", "bounds", "scale", "stats"})
        self.assertEqual((error_map["width"], error_map["height"]), (256, 256))
        half_lat = 150.0 / 111.195
        half_lon = half_lat / np.cos(np.radians(10.0))
        for key, value in (
            ("lat_min", 10.0 - half_lat), ("lat_max", 10.0 + half_lat),
            ("lon_min", 20.0 - half_lon), ("lon_max", 20.0 + half_lon),
        ):
            self.assertAlmostEqual(error_map["bounds"][key], value, places=3)
        self.assertEqual(error_map["scale"], {"min": 0.0, "max": 0.5, "colors": list(maps.ERROR_COLORS)})
        stats = error_map["stats"]
        self.assertEqual(stats["n_points"], 72)
        self.assertAlmostEqual(stats["min"], 0.05, places=4)
        self.assertAlmostEqual(stats["mean"], float(self.error.mean()), places=4)
        self.assertAlmostEqual(stats["max"], 0.405, places=4)

        np.testing.assert_array_equal(
            decode_error_map(error_map["image_base64"]), maps.colorize_error(self.detail.errors, 0.5)
        )


class DetailEdgeCases(unittest.TestCase):
    """Detailed map: 180th meridian, pole, several points in one pixel."""

    def test_points_sharing_a_pixel_keep_the_smaller_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Two points about 300 m apart; a map pixel is about 3 km.
            data = one_feature_dataset(tmp, [0.010, 0.012], [0.012, 0.010], [0.3, 0.1])
            detail = maps.detail_error_grid(
                data, np.float32(ONE_FEATURE["features_norm"]),
                scoring.normalize_weights(ONE_FEATURE["weights"]), 0.0, 0.0, 100.0, 64,
            )
            shown = np.unique(np.round(detail.errors[np.isfinite(detail.errors)], 5))
            np.testing.assert_allclose(shown, [0.1], atol=1e-5)  # the same rule as on the global map
            np.testing.assert_allclose(np.sort(detail.point_errors), [0.1, 0.3], atol=1e-5)
            del data, detail

    def test_window_across_antimeridian(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = one_feature_dataset(tmp, [0.0, 0.0], [179.8, -179.8], [0.1, 0.3])
            result = error_map_detail(data, **ONE_FEATURE, lat=0.0, lon=180.0, radius_km=100.0, size_px=64)
            bounds = result["error_map"]["bounds"]
            self.assertAlmostEqual(bounds["lon_min"], 180.0 - 100.0 / 111.195, places=3)
            self.assertAlmostEqual(bounds["lon_max"], 180.0 + 100.0 / 111.195, places=3)  # beyond 180
            self.assertEqual(result["error_map"]["stats"]["n_points"], 2)

            detail = maps.detail_error_grid(
                data, np.float32(ONE_FEATURE["features_norm"]),
                scoring.normalize_weights(ONE_FEATURE["weights"]), 0.0, 180.0, 100.0, 64,
            )
            deg_x = (detail.lon_max - detail.lon_min) / 64
            west = int((179.8 - detail.lon_min) / deg_x)  # lon 179.8: left of the centre
            east = int((180.2 - detail.lon_min) / deg_x)  # lon -179.8 to 180.2: na prawo
            self.assertLess(west, 32)
            self.assertGreater(east, 32)
            self.assertAlmostEqual(float(detail.errors[32, west]), 0.1, places=5)
            self.assertAlmostEqual(float(detail.errors[32, east]), 0.3, places=5)
            del data, detail

    def test_window_clipped_at_pole(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = one_feature_dataset(tmp, [-89.5, -89.0, -88.0], [0.0, 90.0, -120.0], [0.1, 0.2, 0.3])
            result = error_map_detail(data, **ONE_FEATURE, lat=-89.5, lon=0.0, radius_km=200.0, size_px=64)
            json.dumps(result, allow_nan=False)
            error_map = result["error_map"]
            self.assertEqual(error_map["bounds"]["lat_min"], -90.0)
            self.assertAlmostEqual(error_map["bounds"]["lat_max"], -89.5 + 200.0 / 111.195, places=3)
            # The window includes the pole: full longitude range, height clipped.
            self.assertAlmostEqual(error_map["bounds"]["lon_max"] - error_map["bounds"]["lon_min"], 360.0)
            self.assertEqual(error_map["width"], 64)
            self.assertEqual(error_map["height"], 41)
            self.assertEqual(error_map["stats"]["n_points"], 3)
            self.assertEqual(decode_error_map(error_map["image_base64"]).shape, (41, 64, 4))
            del data


class MapPieces(unittest.TestCase):
    """Parts of the maps that can be checked without Earth data."""

    def test_nearest_source_matches_brute_force(self):
        rng = np.random.default_rng(3)
        for height, width, count, step_x, step_y in (
            (37, 53, 40, 256, 371), (20, 20, 1, 256, 256), (9, 64, 12, 5000, 256), (16, 16, 256, 256, 256),
        ):
            flat = np.sort(rng.choice(height * width, size=count, replace=False))
            rows, columns = np.divmod(flat, width)
            distance = (
                step_x * np.abs(np.arange(width)[None, :, None] - columns[None, None, :])
                + step_y * np.abs(np.arange(height)[:, None, None] - rows[None, None, :])
            )
            with self.subTest(height=height, width=width, count=count):
                # argmin takes the first minimum, i.e. on a tie the lower source number.
                np.testing.assert_array_equal(
                    maps._nearest_source(height, width, flat, step_x, step_y), distance.argmin(axis=2)
                )
        empty = maps._nearest_source(5, 7, np.empty(0, dtype=np.int64), 256, 256)
        np.testing.assert_array_equal(empty, np.full((5, 7), -1))

    def test_error_colors(self):
        grid = np.array([[0.0, 0.5, 0.9, np.nan], [0.1, 0.2, 0.3, 0.4]], dtype=np.float32)
        rgba = maps.colorize_error(grid, 0.5)
        self.assertEqual((rgba.shape, rgba.dtype), ((2, 4, 4), np.uint8))
        self.assertEqual(tuple(rgba[0, 0]), (0x37, 0x13, 0x00, 255))  # error 0: first scale colour
        self.assertEqual(tuple(rgba[0, 1]), (0xFF, 0xE5, 0xD9, 255))  # end of the scale: last colour
        self.assertEqual(tuple(rgba[0, 2]), (0xFF, 0xE5, 0xD9, 255))  # above the scale: still the last
        self.assertEqual(rgba[0, 3, 3], 0)  # no data: transparent
        self.assertTrue((rgba[1, :, 3] == 255).all())

        # 255 distinct colours, increasingly bright: the error can be read from the colour.
        ramp = maps.colorize_error(np.linspace(0.0, 0.5, 255)[None, :], 0.5)[0, :, :3].astype(int)
        self.assertTrue((np.diff(ramp, axis=0) >= 0).all())
        self.assertTrue((np.diff(ramp.sum(axis=1)) > 0).all())

    def test_error_image_decodes_to_the_same_colors(self):
        grid = np.random.default_rng(5).random((40, 60)).astype(np.float32)
        grid[grid > 0.8] = np.nan
        np.testing.assert_array_equal(
            decode_error_map(maps.render_error_map(grid, 0.5)), maps.colorize_error(grid, 0.5)
        )


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
except ImportError:  # no fastapi/httpx in the environment
    TestClient = None


@unittest.skipIf(TestClient is None, "needs the fastapi and httpx packages")
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
                error_map = response.json()["error_map"]
                self.assertEqual(decode_error_map(error_map["image_base64"]).shape, (512, 1024, 4))
                self.assertEqual(error_map["stats"]["n_points"], n)
                spread = client.post("/search", json={**body, "min_distance_km": 3000})
                self.assertEqual(spread.status_code, 200)
                self.assertEqual(client.post("/search", json={**body, "weights": [1.0] * 8}).status_code, 422)
                self.assertEqual(client.post("/search", json={**body, "top_k": 0}).status_code, 422)

    def test_error_map_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            lat, lon = np.meshgrid(9.0 + 0.25 * np.arange(9), 19.0 + 0.25 * np.arange(9), indexing="ij")
            one_feature_dataset(tmp, lat.ravel(), lon.ravel(), 0.05 + 0.005 * np.arange(81))
            os.environ["SZUKACZ_DATA_DIR"] = tmp
            os.environ["SZUKACZ_ERROR_SCALE_MAX"] = "0.4"
            self.addCleanup(os.environ.pop, "SZUKACZ_ERROR_SCALE_MAX")
            from szukacz.api import app

            body = {**ONE_FEATURE, "lat": 10.0, "lon": 20.0}
            with TestClient(app) as client:
                response = client.post("/error-map", json=body)
                self.assertEqual(response.status_code, 200)
                result = response.json()
                self.assertEqual(result["radius_km"], 250.0)  # default values
                self.assertEqual(decode_error_map(result["error_map"]["image_base64"]).shape, (512, 512, 4))
                self.assertEqual(result["error_map"]["stats"]["n_points"], 81)
                self.assertEqual(result["error_map"]["scale"]["max"], 0.4)  # from the environment variable
                # The map from /search uses the same scale.
                found = client.post("/search", json={**ONE_FEATURE, "top_k": 5}).json()
                self.assertEqual(found["error_map"]["scale"], result["error_map"]["scale"])

                small = client.post("/error-map", json={**body, "radius_km": 100, "size_px": 64})
                self.assertEqual(small.status_code, 200)
                self.assertEqual(small.json()["error_map"]["width"], 64)
                for bad in ({"lat": 91}, {"lon": 181}, {"radius_km": 0}, {"size_px": 4096}, {"weights": [1.0] * 8}):
                    with self.subTest(bad=bad):
                        self.assertEqual(client.post("/error-map", json={**body, **bad}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
