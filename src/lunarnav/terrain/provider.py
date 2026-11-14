# ABOUTME: LolaTerrainProvider: the TerrainProvider port backed by LOLA DEMs (decision D24)
# ABOUTME: Picks the finest DEM covering the whole ray disk; converts results to contract models

"""TerrainProvider implementation over LOLA digital elevation models."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np

from lunarnav.contracts import GeoPoint, HorizonMask, TerrainStats
from lunarnav.terrain.dem import Dem, load_lola_cylindrical, load_lola_south_polar
from lunarnav.terrain.horizon import horizon_profile

DEFAULT_RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw" / "lola"
# Decision D24 (check C1): 150 km covers peaks of ~8 km seen over the lunar curvature.
DEFAULT_MAX_DISTANCE_M = 150_000.0
PDS_DATA_SET = "LRO-L-LOLA-4-GDR-V1.0"


class LolaTerrainProvider:
    """Terrain horizon masks (and, with TER-2, slope statistics) from LOLA DEMs.

    Args:
        global_dem: A DEM covering the whole Moon (fallback everywhere).
        regional_dems: Finer DEMs (e.g. south polar tiles); the finest one that contains the
            whole disk of rays around a site is used instead of the global one.
        max_distance_m: Ray length for horizon masks, meters.
    """

    def __init__(
        self,
        global_dem: Dem,
        regional_dems: Sequence[Dem] = (),
        max_distance_m: float = DEFAULT_MAX_DISTANCE_M,
    ):
        """See the class docstring."""
        self.global_dem = global_dem
        self.regional_dems = sorted(regional_dems, key=lambda d: d.resolution_m)
        self.max_distance_m = max_distance_m

    @classmethod
    def from_raw_dir(cls, raw_dir: Path = DEFAULT_RAW_DIR) -> LolaTerrainProvider:
        """Load the D24 products downloaded by ``scripts/terrain_download_dem.py``.

        Args:
            raw_dir: Folder with ``ldem_64.img`` and optionally ``ldem_80s_80m.img``.

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
        return cls(load_lola_cylindrical(global_path, 64), regional)

    def dem_for(self, location: GeoPoint, radius_m: float) -> Dem:
        """Return the finest DEM containing the disk of ``radius_m`` around ``location``."""
        for dem in self.regional_dems:
            if dem.contains(location.lat_deg, location.lon_deg, radius_m):
                return dem
        return self.global_dem

    def horizon_mask(self, location: GeoPoint) -> HorizonMask:
        """Return the terrain horizon elevation around ``location`` at 1 degree azimuth steps.

        Args:
            location: Observer on the Moon. ``height_m`` None means the observer stands on the
                DEM surface; otherwise it is the height above the 1737.4 km sphere, meters.

        Returns:
            The horizon mask; ``location.height_m`` is filled with the observer height used.
        """
        dem = self.dem_for(location, self.max_distance_m)
        observer_h = location.height_m
        if observer_h is None:
            lat, lon = np.array([location.lat_deg]), np.array([location.lon_deg])
            observer_h = float(dem.height_m(lat, lon)[0])
        azimuth, elevation = horizon_profile(
            dem, location.lat_deg, location.lon_deg, observer_h, self.max_distance_m
        )
        return HorizonMask(
            location=location.model_copy(update={"height_m": observer_h}),
            azimuth_deg=azimuth.tolist(),
            horizon_elevation_deg=elevation.tolist(),
            dem_source=f"{dem.name} ({PDS_DATA_SET}), {dem.resolution_m:.0f} m/px",
            dem_resolution_m=dem.resolution_m,
            max_distance_m=self.max_distance_m,
        )

    def terrain_stats(self, location: GeoPoint, radius_m: float) -> TerrainStats:
        """Return elevation and slope statistics over a disk (requirement TER-2, not done yet).

        Raises:
            NotImplementedError: Always, until TER-2.
        """
        raise NotImplementedError("terrain_stats arrives with TER-2")
