# ABOUTME: LolaTerrainProvider: the TerrainProvider port backed by LOLA DEMs (decision D28)
# ABOUTME: Fine DEM near the site, coarser DEM to 150 km (TER-4); results as contract models

"""TerrainProvider implementation over LOLA digital elevation models."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np

from lunarnav.contracts import GeoPoint, HorizonMask, OperationsArea, TerrainStats
from lunarnav.terrain.cache import HorizonCache, cache_key
from lunarnav.terrain.dem import Dem, load_lola_cylindrical, load_lola_south_polar
from lunarnav.terrain.horizon import RaySegment, segmented_horizon_profile
from lunarnav.terrain.reachability import reachable_fraction
from lunarnav.terrain.slope import LANDING_BASELINE_M, slope_grid

DEFAULT_RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw" / "lola"
DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache" / "terrain"
# Decision D28 (check C1): 150 km covers peaks of ~8 km seen over the lunar curvature.
DEFAULT_MAX_DISTANCE_M = 150_000.0
# TER-4: rays read the finest DEM up to this distance and the DEM covering the full ray beyond.
# Raising the eye by dh changes the angle to terrain at distance d by about dh/d, so sub-pixel
# relief of a few meters matters within a few km and is negligible (~0.02 deg) past 10 km.
DEFAULT_NEAR_FIELD_M = 10_000.0
PDS_DATA_SET = "LRO-L-LOLA-4-GDR-V1.0"
# Largest full-disk slope grid, in cells from the center to the edge (grid side 2n + 1). Beyond it
# the cells widen: a 20 km rover range is sampled every 50 m instead of 20 m. Measured: a 20 km
# reachable share at 20 m took 4-9 s per site, too slow for interactive use.
MAX_GRID_RADIUS_CELLS = 400
# At exactly +-90 deg azimuths are undefined (every direction is north or south); computations
# start from this latitude instead, about 3 m from the pole, well below one DEM pixel.
MAX_ABS_LAT_DEG = 90.0 - 1e-4
# An absolute observer height may sit this far below the interpolated DEM surface (LOLA heights
# are quantized to 0.5 m, plus bilinear rounding) before it is rejected as underground.
BELOW_GROUND_TOLERANCE_M = 1.0


def _off_pole(lat_deg: float) -> float:
    """Clamp a latitude away from the exact poles (see MAX_ABS_LAT_DEG)."""
    return float(np.clip(lat_deg, -MAX_ABS_LAT_DEG, MAX_ABS_LAT_DEG))


class LolaTerrainProvider:
    """Terrain horizon masks and slope statistics from LOLA DEMs.

    Args:
        global_dem: A DEM covering the whole Moon (fallback everywhere).
        regional_dems: Finer DEMs (e.g. south polar tiles); the finest one that contains the
            whole disk of rays around a site is used instead of the global one.
        max_distance_m: Ray length for horizon masks, meters.
        cache: Horizon mask cache (TER-5); default an in-memory cache only.
        near_field_m: Ray stretch read on the finest available DEM, meters (TER-4).
    """

    def __init__(
        self,
        global_dem: Dem,
        regional_dems: Sequence[Dem] = (),
        max_distance_m: float = DEFAULT_MAX_DISTANCE_M,
        cache: HorizonCache | None = None,
        near_field_m: float = DEFAULT_NEAR_FIELD_M,
    ):
        """See the class docstring."""
        self.global_dem = global_dem
        self.regional_dems = sorted(regional_dems, key=lambda d: d.resolution_m)
        self.max_distance_m = max_distance_m
        self.cache = cache if cache is not None else HorizonCache()
        self.near_field_m = min(near_field_m, max_distance_m)

    @classmethod
    def from_raw_dir(
        cls,
        raw_dir: Path = DEFAULT_RAW_DIR,
        cache_dir: Path | None = DEFAULT_CACHE_DIR,
    ) -> LolaTerrainProvider:
        """Load the D28 products downloaded by ``scripts/terrain_download_dem.py``.

        Args:
            raw_dir: Folder with ``ldem_64.img`` and optionally the south polar tiles
                ``ldem_80s_80m.img`` and ``ldem_85s_20m.img``.
            cache_dir: Folder for cached horizon masks (git-ignored); None keeps them in memory.

        Returns:
            The provider.

        Raises:
            FileNotFoundError: If the global DEM is missing.
        """
        global_path = raw_dir / "ldem_64.img"
        if not global_path.exists():
            raise FileNotFoundError(
                f"{global_path} missing: run `uv run python scripts/terrain_download_dem.py`"
            )
        regional = []
        polar_path = raw_dir / "ldem_80s_80m.img"
        if polar_path.exists():
            # Size and scale from the ldem_80s_80m.lbl label: 7600 x 7600 samples, 80 m/pixel.
            regional.append(load_lola_south_polar(polar_path, 7600, 80.0))
        fine_path = raw_dir / "ldem_85s_20m.img"
        if fine_path.exists():
            # Size and scale from the ldem_85s_20m.lbl label: 15168 x 15168 samples, 20 m/pixel.
            regional.append(load_lola_south_polar(fine_path, 15168, 20.0))
        global_dem = load_lola_cylindrical(global_path, 64)
        return cls(
            global_dem,
            regional,
            cache=HorizonCache(cache_dir),
        )

    def dem_for(self, location: GeoPoint, radius_m: float) -> Dem:
        """Return the finest DEM containing the disk of ``radius_m`` around ``location``."""
        for dem in self.regional_dems:
            if dem.contains(location.lat_deg, location.lon_deg, radius_m):
                return dem
        return self.global_dem

    def horizon_mask(self, location: GeoPoint, area: OperationsArea) -> HorizonMask:
        """Return the terrain horizon elevation around ``location`` at 1 degree azimuth steps.

        Args:
            location: Observer on the Moon. ``height_m`` None places the observer
                ``area.observer_height_above_ground_m`` above the DEM surface; otherwise it is the
                absolute height above the 1737.4 km sphere, meters.
            area: Operations area; only its observer height is used (decision D32).

        Returns:
            The horizon mask; ``location.height_m`` is filled with the observer height used.

        Raises:
            ValueError: If an absolute ``height_m`` lies below the terrain surface.
        """
        far = self.dem_for(location, self.max_distance_m)
        near = self.dem_for(location, self.near_field_m)
        if near.resolution_m >= far.resolution_m:
            near = far
        lat, lon = np.array([_off_pole(location.lat_deg)]), np.array([location.lon_deg])
        ground_h = float(near.height_m(lat, lon)[0])
        observer_h = location.height_m
        if observer_h is None:
            observer_h = ground_h + area.observer_height_above_ground_m
        elif observer_h < ground_h - BELOW_GROUND_TOLERANCE_M:
            raise ValueError(
                f"observer height {observer_h:.1f} m is below the terrain ({ground_h:.1f} m above "
                f"the 1737.4 km sphere in {near.name}) at {location.lat_deg}, {location.lon_deg}; "
                "leave height_m empty to stand on the surface"
            )
        observer = location.model_copy(update={"height_m": observer_h})
        if near is far:
            segments = [RaySegment(far, 0.0, self.max_distance_m, far.resolution_m)]
            source = self._source(far)
        else:
            segments = [
                RaySegment(near, 0.0, self.near_field_m, near.resolution_m),
                RaySegment(far, self.near_field_m, self.max_distance_m, far.resolution_m),
            ]
            source = (
                f"{self._source(near)} within {self.near_field_m / 1000:.0f} km, "
                f"{self._source(far)} beyond"
            )
        key = cache_key(
            source,
            near.resolution_m,
            location.lat_deg,
            location.lon_deg,
            observer_h,
            self.max_distance_m,
        )
        cached = self.cache.get(key)
        if cached is not None:
            return cached.model_copy(update={"location": observer})
        azimuth, elevation = segmented_horizon_profile(
            segments, _off_pole(location.lat_deg), location.lon_deg, observer_h
        )
        mask = HorizonMask(
            location=observer,
            azimuth_deg=azimuth.tolist(),
            horizon_elevation_deg=elevation.tolist(),
            dem_source=source,
            dem_resolution_m=near.resolution_m,
            max_distance_m=self.max_distance_m,
        )
        self.cache.put(key, mask)
        return mask

    def terrain_stats(self, location: GeoPoint, area: OperationsArea) -> TerrainStats:
        """Return elevation, slope and reachability statistics over the operations area (D32).

        The landing-precision disk (the hard landing constraint) always uses the finest DEM, with
        slopes on a 100 m baseline (decision D36). The full disk (radius ``landing_precision_m +
        operating_range_m``, informational slopes) and the reachable share of the disk of radius
        ``operating_range_m`` (see ``lunarnav.terrain.reachability``) share one grid, whose cells
        widen beyond ``MAX_GRID_RADIUS_CELLS``; their slopes use the pixel baseline. Every
        reported maximum is the 99th percentile over its disk (decision D36).

        Args:
            location: Center of the operations area; its ``height_m`` is ignored.
            area: Landing precision, operating range and traverse slope limit.

        Returns:
            The terrain statistics.
        """
        lat, lon = _off_pole(location.lat_deg), location.lon_deg
        landing_dem = self._dem_for_grid(location, area.landing_precision_m + LANDING_BASELINE_M)
        landing_grid = slope_grid(
            landing_dem, lat, lon, area.landing_precision_m, baseline_m=LANDING_BASELINE_M
        )
        landing = landing_grid.disk_stats(area.landing_precision_m)
        full_radius = area.landing_precision_m + area.operating_range_m
        dem = self._dem_for_grid(location, full_radius)
        spacing = max(dem.resolution_m, full_radius / MAX_GRID_RADIUS_CELLS)
        grid = slope_grid(dem, lat, lon, full_radius, spacing)
        full = grid.disk_stats(full_radius)
        reachable = reachable_fraction(grid, area.operating_range_m, area.traverse_slope_limit_deg)
        source = self._source(landing_dem)
        if dem is not landing_dem or spacing > dem.resolution_m:
            source += f" (landing disk); full disk {dem.name} sampled every {spacing:.0f} m"
        return TerrainStats(
            location=location,
            radius_m=full_radius,
            elevation_m=landing.elevation_m,
            slope_mean_deg=full.slope_mean_deg,
            slope_max_deg=full.slope_max_deg,
            landing_radius_m=area.landing_precision_m,
            landing_slope_mean_deg=landing.slope_mean_deg,
            landing_slope_max_deg=landing.slope_max_deg,
            traverse_slope_limit_deg=area.traverse_slope_limit_deg,
            reachable_fraction=reachable,
            dem_source=source,
            dem_resolution_m=landing_dem.resolution_m,
        )

    def _dem_for_grid(self, location: GeoPoint, radius_m: float) -> Dem:
        """Finest DEM containing a slope grid of ``radius_m`` plus its two-cell border."""
        for dem in self.regional_dems:
            if dem.contains(location.lat_deg, location.lon_deg, radius_m + 2 * dem.resolution_m):
                return dem
        return self.global_dem

    @staticmethod
    def _source(dem: Dem) -> str:
        """Human-readable provenance of a DEM."""
        return f"{dem.name} ({PDS_DATA_SET}), {dem.resolution_m:.0f} m/px"
