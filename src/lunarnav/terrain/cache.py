# ABOUTME: Horizon mask cache (TER-5): bounded in-memory LRU plus optional JSON files on disk
# ABOUTME: Keys hold every input that changes a mask; bump CACHE_VERSION when the algorithm changes

"""Cache of horizon masks, in memory and on disk.

A mask depends only on the DEM, the observer position and height, the ray length and the
algorithm, so it can be reused across requests (date changes, date-slip sweeps, rankings) and
across restarts. Disk entries are written atomically; an unreadable entry is ignored and
recomputed, never trusted.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from collections import OrderedDict
from pathlib import Path

from pydantic import ValidationError

from lunarnav.contracts import HorizonMask

LOGGER = logging.getLogger(__name__)

# Part of every key: increase it whenever the ray casting or the DEM handling changes results.
CACHE_VERSION = 1


def cache_key(
    dem_name: str,
    dem_resolution_m: float,
    lat_deg: float,
    lon_deg: float,
    observer_height_m: float,
    max_distance_m: float,
) -> str:
    """Stable text key of a horizon mask computation (heights rounded to the millimeter)."""
    parts = {
        "v": CACHE_VERSION,
        "dem": dem_name,
        "res": dem_resolution_m,
        "lat": lat_deg,
        "lon": lon_deg,
        "h": round(observer_height_m, 3),
        "dist": max_distance_m,
    }
    return json.dumps(parts, sort_keys=True)


class HorizonCache:
    """Bounded in-memory LRU of horizon masks, backed by an optional folder of JSON files.

    Args:
        directory: Folder for disk entries (created on first write); None keeps memory only.
        max_memory_entries: Masks kept in memory, least recently used dropped first.
    """

    def __init__(self, directory: Path | None = None, max_memory_entries: int = 512):
        """See the class docstring."""
        self.directory = directory
        self.max_memory_entries = max_memory_entries
        self._memory: OrderedDict[str, HorizonMask] = OrderedDict()

    def _path(self, key: str) -> Path:
        assert self.directory is not None
        digest = hashlib.sha1(key.encode()).hexdigest()  # file name only, not security
        return self.directory / f"{digest}.json"

    def get(self, key: str) -> HorizonMask | None:
        """Return the cached mask for ``key``, or None."""
        mask = self._memory.get(key)
        if mask is not None:
            self._memory.move_to_end(key)
            return mask
        if self.directory is None:
            return None
        path = self._path(key)
        if not path.exists():
            return None
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
            if entry.get("key") != key:
                return None
            mask = HorizonMask.model_validate(entry["mask"])
        except (OSError, ValueError, KeyError, ValidationError) as exc:
            LOGGER.warning("ignoring unreadable horizon cache entry %s: %s", path, exc)
            return None
        self._remember(key, mask)
        return mask

    def put(self, key: str, mask: HorizonMask) -> None:
        """Store ``mask`` under ``key`` in memory and, if configured, on disk."""
        self._remember(key, mask)
        if self.directory is None:
            return
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self._path(key)
            tmp = path.with_suffix(f".{os.getpid()}.tmp")
            payload = {"key": key, "mask": mask.model_dump(mode="json")}
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            os.replace(tmp, path)
        except OSError as exc:  # a full or read-only disk must not break an evaluation
            LOGGER.warning("could not write horizon cache entry: %s", exc)

    def _remember(self, key: str, mask: HorizonMask) -> None:
        self._memory[key] = mask
        self._memory.move_to_end(key)
        while len(self._memory) > self.max_memory_entries:
            self._memory.popitem(last=False)
