# ABOUTME: Gridded height models (DEMs): lat/lon to pixel mapping and bilinear height lookup
# ABOUTME: Simple cylindrical (global LOLA LDEM_n) and south polar stereographic (LOLA polar tiles)

"""Digital elevation models on the lunar reference sphere.

A DEM is a 2-D grid of heights above the 1737.4 km sphere. Each concrete class knows how to map
selenographic coordinates to fractional pixel indices (pixel centers are integers); heights
between pixel centers are interpolated bilinearly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

# IAU mean lunar radius; also the reference sphere (OFFSET) of every LOLA GDR label.
MOON_RADIUS_M = 1_737_400.0
# LOLA GDR labels: HEIGHT = DN * SCALING_FACTOR with SCALING_FACTOR = 0.5 m, LSB int16 samples.
LOLA_SCALE_M = 0.5


class Dem(ABC):
    """A height grid with a projection.

    Attributes:
        name: Product name shown to users (e.g. "LOLA LDEM_64").
        heights: Grid of raw values, shape (lines, samples); may be a read-only memmap.
        scale_m: Meters per raw unit (0.5 for LOLA int16 files, 1.0 for float grids).
        resolution_m: Pixel size, meters.
    """

    def __init__(self, name: str, heights: np.ndarray, scale_m: float, resolution_m: float):
        """Store the grid; see the class attributes."""
        if heights.ndim != 2 or min(heights.shape) < 2:
            raise ValueError(f"{name}: need a 2-D grid of at least 2x2, got {heights.shape}")
        self.name = name
        self.heights = heights
        self.scale_m = scale_m
        self.resolution_m = resolution_m

    @abstractmethod
    def pixel(self, lat_deg: np.ndarray, lon_deg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return 0-based fractional (row, col) of each point; integer values are pixel centers."""

    @abstractmethod
    def contains(self, lat_deg: float, lon_deg: float, radius_m: float) -> bool:
        """Return True if the whole disk of ``radius_m`` around the point lies inside the grid."""

    def _wraps_longitude(self) -> bool:
        """Return True when the last column is followed by the first one (global grids)."""
        return False

    def height_m(self, lat_deg: np.ndarray, lon_deg: np.ndarray) -> np.ndarray:
        """Bilinear height above the reference sphere at each point.

        Args:
            lat_deg: Planetocentric latitudes, degrees, any shape.
            lon_deg: East-positive longitudes, degrees, same shape.

        Returns:
            Heights, meters, same shape. Points outside the grid take the nearest edge value.
        """
        row, col = self.pixel(np.asarray(lat_deg, float), np.asarray(lon_deg, float))
        lines, samples = self.heights.shape
        r0 = np.clip(np.floor(row).astype(np.int64), 0, lines - 2)
        fr = np.clip(row - r0, 0.0, 1.0)
        if self._wraps_longitude():
            c0 = np.floor(col).astype(np.int64)
            fc = col - c0
            c0 %= samples
            c1 = (c0 + 1) % samples
        else:
            c0 = np.clip(np.floor(col).astype(np.int64), 0, samples - 2)
            fc = np.clip(col - c0, 0.0, 1.0)
            c1 = c0 + 1
        h = self.heights
        top = h[r0, c0] * (1.0 - fc) + h[r0, c1] * fc
        bottom = h[r0 + 1, c0] * (1.0 - fc) + h[r0 + 1, c1] * fc
        return (top * (1.0 - fr) + bottom * fr) * self.scale_m


class CylindricalDem(Dem):
    """Global simple cylindrical grid starting at 90 N and 0 E (LOLA LDEM_n layout).

    Row 0 is the northernmost line, column 0 the westernmost sample at 0 E; longitudes increase
    eastward and wrap at 360. For LDEM_64 this reproduces the label offsets
    (LINE_PROJECTION_OFFSET 5759.5, SAMPLE_PROJECTION_OFFSET 11519.5 at CENTER_LONGITUDE 180).
    """

    def __init__(self, name: str, heights: np.ndarray, scale_m: float, pixels_per_degree: float):
        """Build the grid; ``heights`` must have shape (180 * ppd, 360 * ppd)."""
        expected = (round(180 * pixels_per_degree), round(360 * pixels_per_degree))
        if heights.shape != expected:
            raise ValueError(
                f"{name}: shape {heights.shape} != {expected} for {pixels_per_degree} ppd"
            )
        resolution_m = np.radians(1.0 / pixels_per_degree) * MOON_RADIUS_M
        super().__init__(name, heights, scale_m, resolution_m)
        self.ppd = pixels_per_degree

    def pixel(self, lat_deg: np.ndarray, lon_deg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """See ``Dem.pixel``."""
        return (90.0 - lat_deg) * self.ppd - 0.5, np.mod(lon_deg, 360.0) * self.ppd - 0.5

    def contains(self, lat_deg: float, lon_deg: float, radius_m: float) -> bool:
        """A global grid contains every disk."""
        return True

    def _wraps_longitude(self) -> bool:
        return True


class SouthPolarStereographicDem(Dem):
    """Square south polar stereographic grid centered on the pole (LOLA LDEM_xxS_yyM layout).

    Projection on the sphere (LOLA GDR catalog DSMAP_POLAR.CAT): rho = 2 R tan((90 - |lat|) / 2),
    x = rho sin(lon), y = -rho cos(lon), 0-based col = x / scale + N/2 - 0.5 (row likewise with y).
    The signs of x and y were checked against LDEM_64 heights (median difference 5.6 m over 2000
    points) and the position of Shackleton crater; the opposite x sign mirrors east and west.
    """

    def __init__(self, name: str, heights: np.ndarray, scale_m: float, resolution_m: float):
        """Build the grid; ``heights`` must be square."""
        if heights.shape[0] != heights.shape[1]:
            raise ValueError(f"{name}: polar grid must be square, got {heights.shape}")
        super().__init__(name, heights, scale_m, resolution_m)
        self.half_width_m = heights.shape[0] / 2 * resolution_m

    def xy_m(self, lat_deg: np.ndarray, lon_deg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Projected (x, y) of each point, meters from the pole."""
        rho = 2.0 * MOON_RADIUS_M * np.tan(np.radians(90.0 - np.abs(lat_deg)) / 2.0)
        lon = np.radians(lon_deg)
        return rho * np.sin(lon), -rho * np.cos(lon)

    def pixel(self, lat_deg: np.ndarray, lon_deg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """See ``Dem.pixel``."""
        x, y = self.xy_m(lat_deg, lon_deg)
        half = self.heights.shape[0] / 2 - 0.5
        return y / self.resolution_m + half, x / self.resolution_m + half

    def contains(self, lat_deg: float, lon_deg: float, radius_m: float) -> bool:
        """True if the disk fits in the square (projection scale ~1 near the pole)."""
        if lat_deg > 0.0:
            return False
        x, y = self.xy_m(np.array(lat_deg), np.array(lon_deg))
        limit = self.half_width_m - self.resolution_m
        return bool(max(abs(float(x)), abs(float(y))) + radius_m <= limit)


def load_lola_cylindrical(path: Path, pixels_per_degree: int) -> CylindricalDem:
    """Memory-map a global LOLA LDEM_<ppd> ``.img`` file (no header, little-endian int16).

    Args:
        path: Path to the ``.img`` file.
        pixels_per_degree: Product resolution, e.g. 64 for LDEM_64.

    Returns:
        The DEM; pixel data stays on disk until read.
    """
    shape = (180 * pixels_per_degree, 360 * pixels_per_degree)
    grid = np.memmap(path, dtype="<i2", mode="r", shape=shape)
    return CylindricalDem(f"LOLA LDEM_{pixels_per_degree}", grid, LOLA_SCALE_M, pixels_per_degree)


def load_lola_south_polar(path: Path, size: int, resolution_m: float) -> SouthPolarStereographicDem:
    """Memory-map a south polar LOLA ``.img`` tile (no header, little-endian int16).

    Args:
        path: Path to the ``.img`` file, e.g. ``ldem_80s_80m.img``.
        size: Lines (= samples) of the square grid, from the label.
        resolution_m: Pixel size, meters, from the label (MAP_SCALE).

    Returns:
        The DEM; pixel data stays on disk until read.
    """
    grid = np.memmap(path, dtype="<i2", mode="r", shape=(size, size))
    name = f"LOLA {path.stem.upper()}"
    return SouthPolarStereographicDem(name, grid, LOLA_SCALE_M, resolution_m)
