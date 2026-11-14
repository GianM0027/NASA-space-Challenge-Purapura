# ABOUTME: JsonSiteCatalog (CAT-2): curated sites from data/catalog/sites.json plus user sites
# ABOUTME: User sites persist in data/user/sites.json (git-ignored), created on the first add

"""Site catalog backed by two JSON files: curated (read-only) and user-defined (read-write)."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import TypeAdapter

from lunarnav.contracts import Site, SiteCatalog

log = logging.getLogger(__name__)

# Relative to the repo root, the API's working directory (README "Run").
DEFAULT_CURATED_PATH = Path("data/catalog/sites.json")
DEFAULT_USER_PATH = Path("data/user/sites.json")

_SITES = TypeAdapter(list[Site])


class JsonSiteCatalog:
    """Curated catalog sites followed by user-added ones.

    Args:
        curated_path: JSON list of curated ``Site`` objects; must exist.
        user_path: JSON list of user sites; created on the first ``add_user_site``.

    Raises:
        FileNotFoundError: If the curated file is missing.
        ValueError: If a file is not a valid list of sites or ids are duplicated.
    """

    def __init__(
        self, curated_path: Path = DEFAULT_CURATED_PATH, user_path: Path = DEFAULT_USER_PATH
    ) -> None:
        """Load both files and check that ids are unique."""
        self.curated_path = Path(curated_path)
        self.user_path = Path(user_path)
        self._curated = _load(self.curated_path)
        self._user = _load(self.user_path) if self.user_path.exists() else []
        seen: set[str] = set()
        for site in self._curated + self._user:
            if site.id in seen:
                raise ValueError(f"duplicate site id {site.id!r} in the catalog files")
            seen.add(site.id)
        log.info("catalog: %d curated, %d user sites", len(self._curated), len(self._user))

    def list_sites(self) -> list[Site]:
        """Return all sites, curated first (file order), then user-added ones (insertion order)."""
        return self._curated + self._user

    def get_site(self, site_id: str) -> Site:
        """Return the site with id ``site_id``.

        Raises:
            KeyError: If no site has that id.
        """
        for site in self._curated + self._user:
            if site.id == site_id:
                return site
        raise KeyError(site_id)

    def add_user_site(self, site: Site) -> Site:
        """Persist a user-defined site and return it.

        Args:
            site: Site to add; its id must be new across curated and user sites.

        Returns:
            The stored site.

        Raises:
            ValueError: If the id already exists.
        """
        if any(s.id == site.id for s in self._curated + self._user):
            raise ValueError(f"site id {site.id!r} already exists")
        self._user.append(site)
        self.user_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.user_path.with_suffix(".tmp")
        tmp.write_bytes(_SITES.dump_json(self._user, indent=2))
        tmp.replace(self.user_path)  # atomic: a crash never leaves a half-written file
        return site


def build_catalog() -> SiteCatalog:
    """Return the site catalog the API wires into the app (spec IF-5).

    Returns:
        A catalog reading ``data/catalog/sites.json`` and ``data/user/sites.json``.
    """
    return JsonSiteCatalog()


def _load(path: Path) -> list[Site]:
    """Read and validate a JSON list of sites, naming the file in any error."""
    try:
        return _SITES.validate_json(path.read_bytes())
    except ValueError as exc:
        raise ValueError(f"invalid site file {path}: {exc}") from exc
