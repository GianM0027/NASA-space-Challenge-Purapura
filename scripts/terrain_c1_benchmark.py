# ABOUTME: Feasibility check C1: times one horizon mask on the LOLA LDEM_64 and LDEM_80S_80M grids
# ABOUTME: Owner: Federico. Prototype for the decision only; real TER-1 code: lunarnav.terrain

"""Measure time and memory of one terrain horizon mask on real LOLA DEMs (check C1).

Run with ``uv run python scripts/terrain_c1_benchmark.py`` after placing the DEMs in
``data/raw/lola/`` (``ldem_64.img`` and ``ldem_80s_80m.img`` from PDS Geosciences).

Method (ray casting on a sphere): from the observer, cast one ray per azimuth; along each ray
sample the DEM every ``step`` meters up to ``max_distance``; for each sample compute the
elevation angle seen by the observer, curvature included; the horizon is the maximum angle.
"""

from __future__ import annotations

import time
import tracemalloc
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# IAU mean radius; also the reference sphere (OFFSET) of the LOLA GDR products (label files).
MOON_RADIUS_M = 1_737_400.0
# LOLA GDR labels: HEIGHT = DN * SCALING_FACTOR, SCALING_FACTOR = 0.5 m, LSB 16-bit integers.
LOLA_SCALE_M = 0.5

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "lola"


@dataclass(frozen=True)
class Dem:
    """A LOLA DEM memory-mapped from disk, with a lat/lon -> fractional pixel mapping.

    Attributes:
        name: Product id.
        heights: Raw DN grid (memory-mapped, int16), shape (lines, samples).
        resolution_m: Pixel size, meters.
        kind: "cylindrical" or "south_polar".
    """

    name: str
    heights: np.memmap
    resolution_m: float
    kind: str

    def pixel(self, lat_deg: np.ndarray, lon_deg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return 0-based fractional (row, col) of each point; pixel centers are integers."""
        if self.kind == "cylindrical":
            # LDEM_64 label: 64 pix/deg, LINE_PROJECTION_OFFSET 5759.5, SAMPLE_PROJECTION_OFFSET
            # 11519.5, CENTER_LONGITUDE 180, longitudes 0..360 east.
            ppd = 64.0
            row = 5759.5 - lat_deg * ppd
            col = 11519.5 + (np.mod(lon_deg, 360.0) - 180.0) * ppd
            return row, col
        # Polar stereographic on the sphere (DSMAP_POLAR.CAT, LOLA GDR catalog):
        # rho = 2*R_moon*tan((90-|lat|)/2), 1-based I = X/scale + N/2 + 0.5 (J likewise with Y).
        # South pole signs X = +rho sin(lon), Y = -rho cos(lon) checked against LDEM_64 heights
        # (median difference 5.6 m) and against Shackleton crater, which a mirrored X misplaces.
        n = self.heights.shape[0]
        rho = 2.0 * MOON_RADIUS_M * np.tan(np.radians(90.0 - np.abs(lat_deg)) / 2.0)
        x = rho * np.sin(np.radians(lon_deg))
        y = -rho * np.cos(np.radians(lon_deg))
        return y / self.resolution_m + n / 2 - 0.5, x / self.resolution_m + n / 2 - 0.5

    def height_m(self, lat_deg: np.ndarray, lon_deg: np.ndarray) -> np.ndarray:
        """Bilinear height above the reference sphere, meters, at each point."""
        row, col = self.pixel(lat_deg, lon_deg)
        lines, samples = self.heights.shape
        r0 = np.clip(np.floor(row).astype(np.int64), 0, lines - 2)
        fr = np.clip(row - r0, 0.0, 1.0)
        if self.kind == "cylindrical":
            c0 = np.floor(col).astype(np.int64)
            fc = col - c0
            c0 %= samples
            c1 = (c0 + 1) % samples  # longitude wraps around
        else:
            c0 = np.clip(np.floor(col).astype(np.int64), 0, samples - 2)
            fc = np.clip(col - c0, 0.0, 1.0)
            c1 = c0 + 1
        h = self.heights
        top = h[r0, c0] * (1 - fc) + h[r0, c1] * fc
        bottom = h[r0 + 1, c0] * (1 - fc) + h[r0 + 1, c1] * fc
        return (top * (1 - fr) + bottom * fr) * LOLA_SCALE_M


def load_dem(name: str, shape: tuple[int, int], resolution_m: float, kind: str) -> Dem:
    """Memory-map one LOLA IMG file (no header, little-endian int16)."""
    path = RAW_DIR / f"{name}.img"
    grid = np.memmap(path, dtype="<i2", mode="r", shape=shape)
    return Dem(name=name, heights=grid, resolution_m=resolution_m, kind=kind)


def destination(
    lat_deg: float, lon_deg: float, azimuth_deg: np.ndarray, distance_m: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Great-circle destination points, shape (n_azimuth, n_distance), degrees.

    Azimuth from local north, clockwise; distances along the reference sphere.
    """
    phi1, lam1 = np.radians(lat_deg), np.radians(lon_deg)
    az = np.radians(azimuth_deg)[:, None]
    delta = (distance_m / MOON_RADIUS_M)[None, :]
    sin_phi2 = np.sin(phi1) * np.cos(delta) + np.cos(phi1) * np.sin(delta) * np.cos(az)
    phi2 = np.arcsin(np.clip(sin_phi2, -1.0, 1.0))
    lam2 = lam1 + np.arctan2(
        np.sin(az) * np.sin(delta) * np.cos(phi1), np.cos(delta) - np.sin(phi1) * sin_phi2
    )
    lon2 = (np.degrees(lam2) + 180.0) % 360.0 - 180.0
    return np.degrees(phi2), lon2


def horizon_mask(
    dem: Dem, lat_deg: float, lon_deg: float, max_distance_m: float, n_azimuth: int = 360
) -> tuple[np.ndarray, np.ndarray, float]:
    """Return (azimuths, horizon elevations, observer height); angles in degrees.

    Elevation angle of a terrain point at angular distance theta, both heights above the sphere:
    horizontal = (R + h) sin(theta), vertical = (R + h) cos(theta) - (R + h_obs);
    the cos(theta) term is the curvature drop (about 2.9 km at 100 km on the Moon).
    """
    azimuth = np.arange(n_azimuth) * (360.0 / n_azimuth)
    distance = np.arange(dem.resolution_m, max_distance_m + 1.0, dem.resolution_m)
    h_obs = float(dem.height_m(np.array([lat_deg]), np.array([lon_deg]))[0])
    lat, lon = destination(lat_deg, lon_deg, azimuth, distance)
    h = dem.height_m(lat, lon)
    theta = distance / MOON_RADIUS_M
    r = MOON_RADIUS_M + h
    angle = np.degrees(np.arctan2(r * np.cos(theta) - (MOON_RADIUS_M + h_obs), r * np.sin(theta)))
    return azimuth, angle.max(axis=1), h_obs


def benchmark(dem: Dem, label: str, lat: float, lon: float, max_distance_m: float) -> None:
    """Time one mask (cold, then best of 3 warm) and report Python-side peak memory."""
    tracemalloc.start()
    t0 = time.perf_counter()
    az, mask, h_obs = horizon_mask(dem, lat, lon, max_distance_m)
    cold = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    warm = []
    for _ in range(3):
        t0 = time.perf_counter()
        horizon_mask(dem, lat, lon, max_distance_m)
        warm.append(time.perf_counter() - t0)
    n_samples = len(az) * int(max_distance_m // dem.resolution_m)
    print(
        f"\n{label} on {dem.name} ({dem.resolution_m:.0f} m/px), "
        f"rays to {max_distance_m / 1e3:.0f} km"
    )
    print(f"  observer height {h_obs:8.1f} m, {n_samples:,} DEM samples")
    print(f"  time: cold {cold:.3f} s, warm best {min(warm):.3f} s; numpy peak {peak / 1e6:.0f} MB")
    print(
        f"  horizon: min {mask.min():5.2f} deg, max {mask.max():5.2f} deg "
        f"(at az {az[mask.argmax()]:.0f}), mean {mask.mean():5.2f} deg"
    )


def main() -> None:
    """Run the C1 measurements."""
    global_dem = load_dem("ldem_64", (11520, 23040), 473.802, "cylindrical")
    polar_dem = load_dem("ldem_80s_80m", (7600, 7600), 80.0, "south_polar")
    # Approximate Apollo 11 area (Mare Tranquillitatis); benchmark point only, not catalog data.
    benchmark(global_dem, "Apollo 11 area", 0.674, 23.473, 150_000.0)
    # Same south polar point as data/examples (-89.5, 0) on both grids: they should roughly agree.
    benchmark(global_dem, "South pole -89.5/0", -89.5, 0.0, 150_000.0)
    benchmark(polar_dem, "South pole -89.5/0", -89.5, 0.0, 150_000.0)


if __name__ == "__main__":
    main()
