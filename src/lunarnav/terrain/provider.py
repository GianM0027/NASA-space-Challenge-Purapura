# ABOUTME: LolaTerrainProvider: the TerrainProvider port backed by LOLA DEMs (decision D28)
# ABOUTME: Fine DEM near the site, coarser DEM to 150 km (TER-4); results as contract models

"""TerrainProvider implementation over LOLA digital elevation models."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np

from lunarnav.contracts import GeoPoint, HorizonMask, TerrainStats
from lunarnav.terrain.cache import HorizonCache, cache_key
from lunarnav.terrain.dem import Dem, load_lola_cylindrical, load_lola_south_polar
from lunarnav.terrain.horizon import RaySegment, segmented_horizon_profile
from lunarnav.terrain.slope import slope_stats

DEFAULT_RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw" / "lola"
DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache" / "terrain"
# Decision D28 (check C1): 150 km covers peaks of ~8 km seen over the lunar curvature.
DEFAULT_MAX_DISTANCE_M = 150_000.0
# TER-4: rays read the finest DEM up to this distance and the DEM covering the full ray beyond.
# Raising the eye by dh changes the angle to terrain at distance d by about dh/d, so sub-pixel
# relief of a few meters matters within a few km and is negligible (~0.02 deg) past 10 km.
DEFAULT_NEAR_FIELD_M = 10_000.0
# Observer (solar panel) height above the ground used by the app, decision D30 (Michael): Glaser et
# al. 2014, Icarus 243, 78, model south-pole illumination at 2 m and 10 m above ground as rover and
# lander solar panel heights; 2 m is the team default, 0 m only a reference case.
DEFAULT_OBSERVER_HEIGHT_ABOVE_GROUND_M = 2.0
PDS_DATA_SET = "LRO-L-LOLA-4-GDR-V1.0"
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
        observer_height_above_ground_m: Height of the observer (solar panel, antenna) above the
            DEM surface when a location has no ``height_m``, meters, >= 0. The horizon is very
            sensitive to it near the ground; 0 (the geometric reference used by the known-answer
            tests) means the observer lies on the surface. The app uses ``from_raw_dir``, whose
            default is 2 m (decision D30, observer height).
        cache: Horizon mask cache (TER-5); default an in-memory cache only.
        near_field_m: Ray stretch read on the finest available DEM, meters (TER-4).
    """

    def __init__(
        self,
        global_dem: Dem,
        regional_dems: Sequence[Dem] = (),
        max_distance_m: float = DEFAULT_MAX_DISTANCE_M,
        observer_height_above_ground_m: float = 0.0,
        cache: HorizonCache | None = None,
        near_field_m: float = DEFAULT_NEAR_FIELD_M,
    ):
        """See the class docstring."""
        if observer_height_above_ground_m < 0.0:
            raise ValueError(
                f"observer_height_above_ground_m {observer_height_above_ground_m} must be >= 0"
            )
        self.global_dem = global_dem
        self.regional_dems = sorted(regional_dems, key=lambda d: d.resolution_m)
        self.max_distance_m = max_distance_m
        self.observer_height_above_ground_m = observer_height_above_ground_m
        self.cache = cache if cache is not None else HorizonCache()
        self.near_field_m = min(near_field_m, max_distance_m)

    @classmethod
    def from_raw_dir(
        cls,
        raw_dir: Path = DEFAULT_RAW_DIR,
        cache_dir: Path | None = DEFAULT_CACHE_DIR,
        observer_height_above_ground_m: float = DEFAULT_OBSERVER_HEIGHT_ABOVE_GROUND_M,
    ) -> LolaTerrainProvider:
        """Load the D28 products downloaded by ``scripts/terrain_download_dem.py``.

        Args:
            raw_dir: Folder with ``ldem_64.img`` and optionally the south polar tiles
                ``ldem_80s_80m.img`` and ``ldem_85s_20m.img``.
            cache_dir: Folder for cached horizon masks (git-ignored); None keeps them in memory.
            observer_height_above_ground_m: Observer height above the DEM surface, meters;
                default 2 m (decision D30, observer height).

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
            observer_height_above_ground_m=observer_height_above_ground_m,
            cache=HorizonCache(cache_dir),
        )

    def dem_for(self, location: GeoPoint, radius_m: float) -> Dem:
        """Return the finest DEM containing the disk of ``radius_m`` around ``location``."""
        for dem in self.regional_dems:
            if dem.contains(location.lat_deg, location.lon_deg, radius_m):
                return dem
        return self.global_dem

    def horizon_mask(self, location: GeoPoint) -> HorizonMask:
        """Return the terrain horizon elevation around ``location`` at 1 degree azimuth steps.

        Args:
            location: Observer on the Moon. ``height_m`` None places the observer
                ``observer_height_above_ground_m`` above the DEM surface; otherwise it is the
                absolute height above the 1737.4 km sphere, meters.

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
            observer_h = ground_h + self.observer_height_above_ground_m
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

    def terrain_stats(self, location: GeoPoint, radius_m: float) -> TerrainStats:
        """Return elevation and slope statistics over a disk (requirement TER-2).

        Slopes are measured over one DEM pixel (see ``lunarnav.terrain.slope``).

        Args:
            location: Disk center; its ``height_m`` is ignored (elevation comes from the DEM).
            radius_m: Disk radius, meters, >= 0 (0 means the center point only).

        Returns:
            The terrain statistics.
        """
        dem = self.dem_for(location, radius_m + 2 * self.global_dem.resolution_m)
        stats = slope_stats(dem, _off_pole(location.lat_deg), location.lon_deg, radius_m)
        return TerrainStats(
            location=location,
            radius_m=radius_m,
            elevation_m=stats.elevation_m,
            slope_mean_deg=stats.slope_mean_deg,
            slope_max_deg=stats.slope_max_deg,
            dem_source=self._source(dem),
            dem_resolution_m=dem.resolution_m,
        )

    @staticmethod
    def _source(dem: Dem) -> str:
        """Human-readable provenance of a DEM."""
        return f"{dem.name} ({PDS_DATA_SET}), {dem.resolution_m:.0f} m/px"
