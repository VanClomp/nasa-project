"""Loading the precomputed Earth data from the /data/earth folder.

The files come from the Precomputer (spec, section 4.1):
    earth_features_norm.npy   (N_POINTS, 12, K) float32, features in [0, 1]
    earth_features_raw.npy    (N_POINTS, 12, K) float32, physical values
    earth_metadata.parquet    or earth_metadata.npy (structured array)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .scoring import latlon_to_unit_xyz

N_MONTHS = 12
HEATMAP_WIDTH = 1024
HEATMAP_HEIGHT = 512

# Feature order from section 4.2 of the spec (indices of the matrices' axis 2).
K_FEATURES = (
    "temp_mean",
    "temp_diurnal_amp",
    "thermal_inertia",
    "surface_roughness",
    "soil_moisture",
    "dust_aerosol",
    "solar_elevation_max",
    "radiation_proxy",
    "slope_deg",
)

_REQUIRED_COLUMNS = ("id", "lat", "lon", "px_x", "px_y", "nearest_cave_km")


@dataclass(frozen=True)
class EarthData:
    """Earth data in memory; index `i` is the same point in every array."""

    features_norm: np.ndarray  # (N, 12, K) float32, read-only mmap
    features_raw: np.ndarray  # (N, 12, K) float32, read-only mmap
    feature_keys: tuple[str, ...]  # K feature names
    ids: np.ndarray  # (N,) int64
    lat: np.ndarray  # (N,) float64, degrees
    lon: np.ndarray  # (N,) float64, degrees
    nearest_cave_km: np.ndarray  # (N,) float64
    unit_xyz: np.ndarray  # (N, 3) float64, points as unit vectors
    # Grouping of points by pixels of the 1024x512 heatmap:
    pixel_order: np.ndarray  # (N,) point indices sorted by pixel
    pixel_starts: np.ndarray  # (P,) group starts in pixel_order
    pixel_flat: np.ndarray  # (P,) pixel number of each group: px_y * 1024 + px_x

    @property
    def n_points(self) -> int:
        return self.features_norm.shape[0]

    @property
    def n_features(self) -> int:
        return self.features_norm.shape[2]


def _read_metadata(data_dir: Path) -> dict[str, np.ndarray]:
    parquet_path = data_dir / "earth_metadata.parquet"
    npy_path = data_dir / "earth_metadata.npy"
    if parquet_path.exists():
        import pyarrow.parquet as pq  # imported here: the .npy variant does not need pyarrow

        table = pq.read_table(parquet_path)
        return {name: table.column(name).to_numpy() for name in table.column_names}
    if npy_path.exists():
        records = np.load(npy_path, allow_pickle=False)
        if records.dtype.names is None:
            raise ValueError(f"{npy_path}: expected a structured array with named columns")
        return {name: records[name] for name in records.dtype.names}
    raise FileNotFoundError(f"Metadata file not found: neither {parquet_path} nor {npy_path}")


def load_earth_data(data_dir: str | Path) -> EarthData:
    """Memory-maps the .npy matrices (mmap) and loads the point metadata.

    Raises FileNotFoundError when a file is missing, and ValueError when shapes
    or columns do not match the spec.
    """
    data_dir = Path(data_dir)
    features_norm = np.load(data_dir / "earth_features_norm.npy", mmap_mode="r")
    features_raw = np.load(data_dir / "earth_features_raw.npy", mmap_mode="r")

    if features_norm.ndim != 3 or features_norm.shape[1] != N_MONTHS:
        raise ValueError(
            f"earth_features_norm.npy: expected shape (N, {N_MONTHS}, K), got {features_norm.shape}"
        )
    if features_raw.shape != features_norm.shape:
        raise ValueError(
            f"earth_features_raw.npy has shape {features_raw.shape}, but norm has {features_norm.shape}"
        )
    for name, array in (("norm", features_norm), ("raw", features_raw)):
        if not np.issubdtype(array.dtype, np.floating):
            raise ValueError(f"earth_features_{name}.npy: expected float32, got {array.dtype}")
    n_points, _, n_features = features_norm.shape

    meta = _read_metadata(data_dir)
    missing = [name for name in _REQUIRED_COLUMNS if name not in meta]
    if missing:
        raise ValueError(f"Earth metadata: missing columns {missing}")
    for name in _REQUIRED_COLUMNS:
        if meta[name].shape != (n_points,):
            raise ValueError(
                f"Earth metadata: column {name} has shape {meta[name].shape}, expected ({n_points},)"
            )

    lat = meta["lat"].astype(np.float64)
    lon = meta["lon"].astype(np.float64)
    if not (np.isfinite(lat).all() and np.isfinite(lon).all()):
        raise ValueError("Earth metadata: lat/lon contain infinite values or NaN")

    px_x = meta["px_x"].astype(np.int64)
    px_y = meta["px_y"].astype(np.int64)
    if n_points and (
        px_x.min() < 0 or px_x.max() >= HEATMAP_WIDTH or px_y.min() < 0 or px_y.max() >= HEATMAP_HEIGHT
    ):
        raise ValueError(
            f"Earth metadata: px_x/px_y outside the {HEATMAP_WIDTH}x{HEATMAP_HEIGHT} grid"
        )
    flat = px_y * HEATMAP_WIDTH + px_x
    pixel_order = np.argsort(flat, kind="stable")
    pixel_flat, pixel_starts = np.unique(flat[pixel_order], return_index=True)

    if n_features == len(K_FEATURES):
        feature_keys = K_FEATURES
    else:
        feature_keys = tuple(f"feature_{k}" for k in range(n_features))

    return EarthData(
        features_norm=features_norm,
        features_raw=features_raw,
        feature_keys=feature_keys,
        ids=meta["id"].astype(np.int64),
        lat=lat,
        lon=lon,
        nearest_cave_km=meta["nearest_cave_km"].astype(np.float64),
        unit_xyz=latlon_to_unit_xyz(lat, lon),
        pixel_order=pixel_order,
        pixel_starts=pixel_starts,
        pixel_flat=pixel_flat,
    )
