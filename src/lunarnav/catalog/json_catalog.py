# ABOUTME: JsonSiteCatalog (CAT-2, D34): curated sites from data/catalog/sites.json plus user sites
# ABOUTME: User sites persist in data/user/sites.json (git-ignored); add, rename, remove are atomic

"""Site catalog backed by two JSON files: curated (read-only) and user-defined (read-write).

Several processes may share the user file (e.g. two dev servers). Every change therefore takes a
lock file, re-reads the user file from disk, applies the change and rewrites it atomically, and
reads pick up changes made by other processes (file modification stamp), so no process overwrites
another's additions.
"""

from __future__ import annotations

import contextlib
import logging
import os
import time
from collections.abc import Callable, Iterator
from pathlib import Path

from pydantic import TypeAdapter

from lunarnav.contracts import (
    DuplicateSiteError,
    Origin,
    ReadOnlySiteError,
    Site,
    SiteCatalog,
    UnknownSiteError,
)

log = logging.getLogger(__name__)

# Relative to the repo root, the API's working directory (README "Run").
DEFAULT_CURATED_PATH = Path("data/catalog/sites.json")
DEFAULT_USER_PATH = Path("data/user/sites.json")

LOCK_TIMEOUT_S = 5.0  # give up waiting for another process after this long
LOCK_STALE_S = 30.0  # a lock older than this was left by a crashed process and is removed

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
        self._user: list[Site] = []
        self._user_stamp: tuple[int, int] | None = None
        self._refresh_user()
        log.info("catalog: %d curated, %d user sites", len(self._curated), len(self._user))

    def list_sites(self) -> list[Site]:
        """Return all sites, curated first (file order), then user-added ones (insertion order)."""
        self._refresh_user()
        return self._curated + self._user

    def get_site(self, site_id: str) -> Site:
        """Return the site with id ``site_id``.

        Raises:
            UnknownSiteError: If no site has that id (a ``KeyError``).
        """
        for site in self.list_sites():
            if site.id == site_id:
                return site
        raise UnknownSiteError(site_id)

    def add_user_site(self, site: Site) -> Site:
        """Persist a user-defined site and return it.

        Args:
            site: Site to add; its id must be new across curated and user sites.

        Returns:
            The stored site.

        Raises:
            DuplicateSiteError: If the id already exists (a ``ValueError``).
        """

        def change(user: list[Site]) -> Site:
            if any(s.id == site.id for s in self._curated + user):
                raise DuplicateSiteError(f"site id {site.id!r} already exists")
            user.append(site)
            return site

        return self._update_user(change)

    def remove_user_site(self, site_id: str) -> None:
        """Delete a user-defined site, persistently.

        Args:
            site_id: Id of the site to delete.

        Raises:
            UnknownSiteError: If no site has that id.
            ReadOnlySiteError: If the site is curated (``origin != "user"``).
        """

        def change(user: list[Site]) -> None:
            index = self._user_index(user, site_id)
            del user[index]

        self._update_user(change)

    def rename_user_site(self, site_id: str, name: str) -> Site:
        """Change the display name of a user-defined site, persistently; the id stays the same.

        Args:
            site_id: Id of the site to rename.
            name: New display name; leading and trailing whitespace is stripped.

        Returns:
            The updated site.

        Raises:
            UnknownSiteError: If no site has that id.
            ReadOnlySiteError: If the site is curated (``origin != "user"``).
            ValueError: If ``name`` is empty after stripping.
        """
        new_name = name.strip()
        if not new_name:
            raise ValueError("site name must not be blank")

        def change(user: list[Site]) -> Site:
            index = self._user_index(user, site_id)
            renamed = user[index].model_copy(update={"name": new_name})
            user[index] = renamed
            return renamed

        return self._update_user(change)

    # --- internals -------------------------------------------------------------------------------

    def _user_index(self, user: list[Site], site_id: str) -> int:
        """Return the position of a user site, or raise the contract error for the id."""
        for i, site in enumerate(user):
            if site.id == site_id:
                if site.origin is not Origin.USER:  # hand-edited file: still never modify it
                    raise ReadOnlySiteError(f"site {site_id!r} is not a user site")
                return i
        if any(s.id == site_id for s in self._curated):
            raise ReadOnlySiteError(f"site {site_id!r} is curated and cannot be changed")
        raise UnknownSiteError(site_id)

    def _update_user[T](self, change: Callable[[list[Site]], T]) -> T:
        """Apply ``change`` to the user sites on disk under the lock and write them back."""
        with _file_lock(self.user_path.with_name(self.user_path.name + ".lock")):
            user = _load(self.user_path) if self.user_path.exists() else []
            result = change(user)
            self.user_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.user_path.with_name(f"{self.user_path.name}.{os.getpid()}.tmp")
            tmp.write_bytes(_SITES.dump_json(user, indent=2))
            _replace(tmp, self.user_path)  # atomic: readers never see a half-written file
            self._user = user
            self._user_stamp = _stamp(self.user_path)
        return result

    def _refresh_user(self) -> None:
        """Reload the user file if another process changed it since the last read."""
        stamp = _stamp(self.user_path)
        if stamp == self._user_stamp:
            return
        self._user = _load(self.user_path) if stamp is not None else []
        self._user_stamp = stamp
        curated_ids = {s.id for s in self._curated}
        seen: set[str] = set()
        for site in self._user:
            if site.id in curated_ids or site.id in seen:
                raise ValueError(f"duplicate site id {site.id!r} in the catalog files")
            seen.add(site.id)


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


def _stamp(path: Path) -> tuple[int, int] | None:
    """Modification time (ns) and size of a file, or None if it does not exist."""
    try:
        st = path.stat()
    except FileNotFoundError:
        return None
    return (st.st_mtime_ns, st.st_size)


@contextlib.contextmanager
def _file_lock(lock: Path) -> Iterator[None]:
    """Cross-process exclusive lock: a lock file created atomically, removed on exit."""
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + LOCK_TIMEOUT_S
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            with contextlib.suppress(FileNotFoundError):
                if time.time() - lock.stat().st_mtime > LOCK_STALE_S:
                    lock.unlink()  # left behind by a crashed process
                    continue
            if time.monotonic() > deadline:
                raise TimeoutError(f"could not lock {lock} within {LOCK_TIMEOUT_S} s") from None
            time.sleep(0.02)
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            lock.unlink()


def _replace(src: Path, dst: Path) -> None:
    """Rename ``src`` over ``dst``, retrying briefly while a reader holds ``dst`` open (Windows)."""
    for attempt in range(50):
        try:
            src.replace(dst)
            return
        except PermissionError:
            if attempt == 49:
                raise
            time.sleep(0.02)
