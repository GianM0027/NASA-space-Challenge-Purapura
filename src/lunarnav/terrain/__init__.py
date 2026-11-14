# ABOUTME: terrain module: terrain horizon masks and slope statistics from LOLA topography
# ABOUTME: Owner: Federico (MISSION.md section 4); public API uses lunarnav.contracts types only

"""Terrain horizon masks and slope statistics from LOLA topography."""

from lunarnav.contracts import TerrainProvider
from lunarnav.terrain.provider import LolaTerrainProvider


def build_terrain_provider() -> TerrainProvider:
    """Build the terrain provider the API wires in (spec IF-5, decision D21).

    Returns:
        A LolaTerrainProvider over the DEMs in ``data/raw/lola/``.

    Raises:
        FileNotFoundError: If the DEMs were not downloaded (the API then shows the placeholder).
    """
    return LolaTerrainProvider.from_raw_dir()


__all__ = ["LolaTerrainProvider", "build_terrain_provider"]
