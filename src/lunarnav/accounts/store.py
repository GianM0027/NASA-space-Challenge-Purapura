# ABOUTME: SQLite store of accounts, sessions, personal sites, proposals and community sites (D45)
# ABOUTME: Owner: Gian. One file, one short connection per operation; safe for the API's thread pool

"""Accounts and everything a person saves on the server.

* A **guest** is an anonymous account created on a visitor's first save; its session cookie ends
  with the browser session and the server forgets it after ``GUEST_TTL``.
* A **registered** account has a username and a password (scrypt, see ``passwords``); its
  session lasts ``SESSION_TTL``. Registering from a guest session keeps the guest's sites, and
  logging in from one moves them into the account.
* Sites saved by a person are private to their account. A registered person may **propose**
  one of them for the shared catalog; an admin approves it (it becomes a community site that
  everyone sees) or rejects it.

Session tokens are random and only their SHA-256 is stored, so the database never holds a
usable cookie.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from lunarnav.accounts.passwords import DUMMY_HASH, hash_password, verify_password
from lunarnav.contracts import Origin, Site
from lunarnav.contracts.errors import DuplicateSiteError, UnknownSiteError

SESSION_TTL = timedelta(days=30)
GUEST_TTL = timedelta(days=2)
MAX_SITES_PER_ACCOUNT = 200
MAX_PENDING_PROPOSALS = 5
MAX_NOTE_CHARS = 1000
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,31}$")
MIN_PASSWORD_CHARS = 8
MAX_PASSWORD_CHARS = 256

ProposalStatus = Literal["pending", "approved", "rejected"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    username_key TEXT UNIQUE,
    password_hash TEXT,
    is_guest INTEGER NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS user_sites (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    site_id TEXT NOT NULL,
    site_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, site_id)
);
CREATE TABLE IF NOT EXISTS proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    username TEXT NOT NULL,
    site_json TEXT NOT NULL,
    note TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at TEXT NOT NULL,
    decided_at TEXT,
    admin_note TEXT NOT NULL DEFAULT '',
    community_site_id TEXT
);
CREATE TABLE IF NOT EXISTS community_sites (
    site_id TEXT PRIMARY KEY,
    site_json TEXT NOT NULL,
    proposal_id INTEGER,
    approved_at TEXT NOT NULL
);
"""


class AccountError(ValueError):
    """A request about accounts that cannot be satisfied; the message is safe to show."""


class UsernameTakenError(AccountError):
    """The username is already registered (HTTP 409)."""


class AccountLimitError(AccountError):
    """A per-account limit (sites, pending proposals) is reached (HTTP 409)."""


@dataclass(frozen=True)
class User:
    """An account as the API sees it.

    Attributes:
        id: Database id.
        username: Display name; None for a guest.
        is_guest: Anonymous account of one browser session.
        is_admin: May review site proposals.
    """

    id: int
    username: str | None
    is_guest: bool
    is_admin: bool


@dataclass(frozen=True)
class Proposal:
    """A request to add a site to the shared catalog.

    Attributes:
        id: Database id.
        username: Who proposed it (kept if the account is deleted later).
        site: The site as proposed.
        note: Why it should be added, sources, anything for the reviewer.
        status: "pending", "approved" or "rejected".
        created_at: When it was proposed.
        decided_at: When it was approved or rejected.
        admin_note: The reviewer's note to the proposer.
        community_site_id: Id of the catalog site created on approval.
    """

    id: int
    username: str
    site: Site
    note: str
    status: ProposalStatus
    created_at: datetime
    decided_at: datetime | None
    admin_note: str
    community_site_id: str | None


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(moment: datetime) -> str:
    return moment.isoformat()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def check_username(username: str) -> str:
    """Return the trimmed username or raise ``AccountError`` with what is wrong."""
    name = username.strip()
    if not USERNAME_PATTERN.fullmatch(name):
        raise AccountError(
            "Usernames have 3 to 32 characters: letters, digits, '.', '_' or '-', "
            "starting with a letter or digit."
        )
    return name


def check_password(password: str) -> str:
    """Return the password or raise ``AccountError`` when it is too short or too long."""
    if len(password) < MIN_PASSWORD_CHARS:
        raise AccountError(f"Passwords need at least {MIN_PASSWORD_CHARS} characters.")
    if len(password) > MAX_PASSWORD_CHARS:
        raise AccountError(f"Passwords have at most {MAX_PASSWORD_CHARS} characters.")
    return password


def _slug(text: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")[:60] or "site"


class AccountStore:
    """All account data in one SQLite file.

    Attributes:
        path: Database file (created with its folder when missing).
    """

    def __init__(self, path: Path) -> None:
        """Open (and create if needed) the database at ``path``."""
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        self._admin_keys: set[str] = set()
        with self._db() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(_SCHEMA)

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        """One connection and one transaction, committed on success, rolled back on error."""
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            with self._write_lock, db:
                yield db

    # --- Accounts and sessions -------------------------------------------------------------

    @staticmethod
    def _user(row: sqlite3.Row) -> User:
        return User(row["id"], row["username"], bool(row["is_guest"]), bool(row["is_admin"]))

    def create_guest(self) -> User:
        """Create an anonymous account for one browser session."""
        with self._db() as db:
            cursor = db.execute(
                "INSERT INTO users (is_guest, created_at) VALUES (1, ?)", (_iso(_now()),)
            )
            return User(int(cursor.lastrowid or 0), None, True, False)

    def register(self, username: str, password: str, guest: User | None = None) -> User:
        """Create a registered account, or turn ``guest`` into one (keeping its sites).

        Raises:
            AccountError: Invalid username or password.
            UsernameTakenError: The username exists (case-insensitive).
        """
        name = check_username(username)
        password_hash = hash_password(check_password(password))
        admin = int(name.lower() in self._admin_keys)
        with self._db() as db:
            if db.execute("SELECT 1 FROM users WHERE username_key = ?", (name.lower(),)).fetchone():
                raise UsernameTakenError("This username is taken: choose another one.")
            if guest is not None and guest.is_guest:
                db.execute(
                    "UPDATE users SET username = ?, username_key = ?, password_hash = ?, "
                    "is_guest = 0, is_admin = ? WHERE id = ? AND is_guest = 1",
                    (name, name.lower(), password_hash, admin, guest.id),
                )
                db.execute("DELETE FROM sessions WHERE user_id = ?", (guest.id,))
                return User(guest.id, name, False, bool(admin))
            cursor = db.execute(
                "INSERT INTO users (username, username_key, password_hash, is_guest, is_admin, "
                "created_at) VALUES (?, ?, ?, 0, ?, ?)",
                (name, name.lower(), password_hash, admin, _iso(_now())),
            )
            return User(int(cursor.lastrowid or 0), name, False, bool(admin))

    def authenticate(self, username: str, password: str) -> User | None:
        """Return the account if the username and password match, else None."""
        with self._db() as db:
            row = db.execute(
                "SELECT * FROM users WHERE username_key = ? AND is_guest = 0",
                (username.strip().lower(),),
            ).fetchone()
        if row is None:
            verify_password(password, DUMMY_HASH)  # same time as a wrong password
            return None
        return self._user(row) if verify_password(password, row["password_hash"]) else None

    def create_session(self, user: User) -> str:
        """Start a session for ``user`` and return its token (the cookie value)."""
        token = secrets.token_urlsafe(32)
        expires = _now() + (GUEST_TTL if user.is_guest else SESSION_TTL)
        with self._db() as db:
            db.execute(
                "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                (_token_hash(token), user.id, _iso(expires)),
            )
        return token

    def user_for_token(self, token: str) -> User | None:
        """Return the account of a live session, or None for an unknown or expired token."""
        with self._db() as db:
            row = db.execute(
                "SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id "
                "WHERE sessions.token_hash = ? AND sessions.expires_at > ?",
                (_token_hash(token), _iso(_now())),
            ).fetchone()
        return self._user(row) if row else None

    def end_session(self, token: str) -> None:
        """Forget one session (log out)."""
        with self._db() as db:
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))

    def merge_guest(self, guest: User, into: User) -> int:
        """Move a guest's sites into ``into`` (skipping ids it already has), then delete the guest.

        Returns:
            How many sites were moved.
        """
        if not guest.is_guest or guest.id == into.id:
            return 0
        with self._db() as db:
            free = (
                MAX_SITES_PER_ACCOUNT
                - db.execute(
                    "SELECT COUNT(*) FROM user_sites WHERE user_id = ?", (into.id,)
                ).fetchone()[0]
            )
            rows = db.execute(
                "SELECT site_id FROM user_sites WHERE user_id = ? AND site_id NOT IN "
                "(SELECT site_id FROM user_sites WHERE user_id = ?) ORDER BY created_at",
                (guest.id, into.id),
            ).fetchall()
            moved = [row["site_id"] for row in rows[: max(free, 0)]]
            db.executemany(
                "UPDATE user_sites SET user_id = ? WHERE user_id = ? AND site_id = ?",
                [(into.id, guest.id, site_id) for site_id in moved],
            )
            db.execute("DELETE FROM users WHERE id = ? AND is_guest = 1", (guest.id,))
        return len(moved)

    def delete_account(self, user: User) -> None:
        """Delete an account with its sites, sessions and pending proposals.

        Decided proposals stay (with the username), as the history of the catalog.
        """
        with self._db() as db:
            db.execute("DELETE FROM proposals WHERE user_id = ? AND status = 'pending'", (user.id,))
            db.execute("DELETE FROM users WHERE id = ?", (user.id,))

    def set_admins(self, usernames: list[str]) -> None:
        """Make exactly these usernames admins (case-insensitive), now and when they register."""
        keys = [name.strip().lower() for name in usernames if name.strip()]
        self._admin_keys = set(keys)
        with self._db() as db:
            db.execute("UPDATE users SET is_admin = 0")
            db.executemany(
                "UPDATE users SET is_admin = 1 WHERE username_key = ?", [(k,) for k in keys]
            )

    def purge_expired(self) -> None:
        """Delete expired sessions and guests left without a session."""
        with self._db() as db:
            db.execute("DELETE FROM sessions WHERE expires_at <= ?", (_iso(_now()),))
            db.execute(
                "DELETE FROM users WHERE is_guest = 1 AND id NOT IN (SELECT user_id FROM sessions)"
            )

    # --- Personal sites --------------------------------------------------------------------

    def list_sites(self, user: User) -> list[Site]:
        """The account's own sites, oldest first."""
        with self._db() as db:
            rows = db.execute(
                "SELECT site_json FROM user_sites WHERE user_id = ? ORDER BY created_at", (user.id,)
            ).fetchall()
        return [Site.model_validate_json(row["site_json"]) for row in rows]

    def add_site(self, user: User, site: Site) -> Site:
        """Save a personal site.

        Raises:
            DuplicateSiteError: The account already has a site with this id.
            AccountLimitError: The account has ``MAX_SITES_PER_ACCOUNT`` sites.
        """
        with self._db() as db:
            count = db.execute(
                "SELECT COUNT(*) FROM user_sites WHERE user_id = ?", (user.id,)
            ).fetchone()[0]
            if count >= MAX_SITES_PER_ACCOUNT:
                raise AccountLimitError(
                    f"You can save at most {MAX_SITES_PER_ACCOUNT} sites: delete one first."
                )
            try:
                db.execute(
                    "INSERT INTO user_sites (user_id, site_id, site_json, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (user.id, site.id, site.model_dump_json(), _iso(_now())),
                )
            except sqlite3.IntegrityError as error:
                raise DuplicateSiteError(f"site id {site.id!r} already exists") from error
        return site

    def get_site(self, user: User, site_id: str) -> Site:
        """One personal site; ``UnknownSiteError`` if the account has none with this id."""
        with self._db() as db:
            row = db.execute(
                "SELECT site_json FROM user_sites WHERE user_id = ? AND site_id = ?",
                (user.id, site_id),
            ).fetchone()
        if row is None:
            raise UnknownSiteError(site_id)
        return Site.model_validate_json(row["site_json"])

    def update_site(
        self, user: User, site_id: str, *, name: str | None = None, description: str | None = None
    ) -> Site:
        """Change a personal site's name and/or description (None keeps a field).

        Raises:
            UnknownSiteError: No such personal site.
            ValueError: Blank name.
        """
        site = self.get_site(user, site_id)
        update: dict[str, str] = {}
        if name is not None:
            if not name.strip():
                raise ValueError("the name cannot be blank")
            update["name"] = name.strip()
        if description is not None:
            update["description"] = description.strip()
        updated = site.model_copy(update=update)
        with self._db() as db:
            db.execute(
                "UPDATE user_sites SET site_json = ? WHERE user_id = ? AND site_id = ?",
                (updated.model_dump_json(), user.id, site_id),
            )
        return updated

    def remove_site(self, user: User, site_id: str) -> None:
        """Delete a personal site; ``UnknownSiteError`` if there is none."""
        with self._db() as db:
            cursor = db.execute(
                "DELETE FROM user_sites WHERE user_id = ? AND site_id = ?", (user.id, site_id)
            )
        if cursor.rowcount == 0:
            raise UnknownSiteError(site_id)

    # --- Proposals and community sites -----------------------------------------------------

    @staticmethod
    def _proposal(row: sqlite3.Row) -> Proposal:
        decided = row["decided_at"]
        return Proposal(
            id=row["id"],
            username=row["username"],
            site=Site.model_validate_json(row["site_json"]),
            note=row["note"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            decided_at=datetime.fromisoformat(decided) if decided else None,
            admin_note=row["admin_note"],
            community_site_id=row["community_site_id"],
        )

    def propose(self, user: User, site_id: str, note: str) -> Proposal:
        """Propose one of the account's own sites for the shared catalog.

        Raises:
            AccountError: Guest account, note too long, or this site is already pending.
            AccountLimitError: ``MAX_PENDING_PROPOSALS`` proposals are already pending.
            UnknownSiteError: The account has no site with this id.
        """
        if user.is_guest or user.username is None:
            raise AccountError("Create an account to propose sites for the catalog.")
        if len(note) > MAX_NOTE_CHARS:
            raise AccountError(f"The note has at most {MAX_NOTE_CHARS} characters.")
        site = self.get_site(user, site_id)
        with self._db() as db:
            pending = db.execute(
                "SELECT site_json FROM proposals WHERE user_id = ? AND status = 'pending'",
                (user.id,),
            ).fetchall()
            if any(Site.model_validate_json(r["site_json"]).id == site.id for r in pending):
                raise AccountError("This site is already waiting for review.")
            if len(pending) >= MAX_PENDING_PROPOSALS:
                raise AccountLimitError(
                    f"You can have at most {MAX_PENDING_PROPOSALS} proposals waiting for review."
                )
            cursor = db.execute(
                "INSERT INTO proposals (user_id, username, site_json, note, status, created_at) "
                "VALUES (?, ?, ?, ?, 'pending', ?)",
                (user.id, user.username, site.model_dump_json(), note.strip(), _iso(_now())),
            )
            row = db.execute("SELECT * FROM proposals WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return self._proposal(row)

    def list_proposals(
        self, user: User | None = None, status: ProposalStatus | None = None
    ) -> list[Proposal]:
        """Proposals, newest first: one account's when ``user`` is given, else everyone's."""
        query = "SELECT * FROM proposals WHERE 1 = 1"
        args: list[object] = []
        if user is not None:
            query += " AND user_id = ?"
            args.append(user.id)
        if status is not None:
            query += " AND status = ?"
            args.append(status)
        with self._db() as db:
            rows = db.execute(query + " ORDER BY id DESC", args).fetchall()
        return [self._proposal(row) for row in rows]

    def _pending(self, db: sqlite3.Connection, proposal_id: int) -> sqlite3.Row:
        row = db.execute("SELECT * FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        if row["status"] != "pending":
            raise AccountError("This proposal was already reviewed.")
        return row

    def approve(
        self,
        proposal_id: int,
        taken_ids: set[str],
        *,
        name: str | None = None,
        description: str | None = None,
        sources: list[str] | None = None,
        admin_note: str = "",
    ) -> Proposal:
        """Approve a proposal: its site joins the shared catalog as a community site.

        The catalog site gets the id ``community-<slug>`` (made unique against ``taken_ids`` and
        existing community sites), origin "other", status "candidate", and the given name,
        description and sources (defaults: the proposal's; sources default to a line naming the
        proposal, since every catalog site needs one).

        Raises:
            KeyError: Unknown proposal.
            AccountError: Already reviewed.
        """
        now = _now()
        with self._db() as db:
            row = self._pending(db, proposal_id)
            proposed = Site.model_validate_json(row["site_json"])
            existing = {r["site_id"] for r in db.execute("SELECT site_id FROM community_sites")}
            base = "community-" + _slug(proposed.id.removeprefix("user-"))
            site_id, n = base, 2
            while site_id in existing or site_id in taken_ids:
                site_id, n = f"{base}-{n}", n + 1
            cited = [s.strip() for s in (sources or []) if s.strip()]
            site = Site(
                id=site_id,
                name=(name or proposed.name).strip() or proposed.name,
                location=proposed.location,
                origin=Origin.OTHER,
                status="candidate",
                description=(proposed.description if description is None else description).strip(),
                sources=cited
                or [
                    f"LunarNav community proposal #{proposal_id} by {row['username']}, "
                    f"approved {now.date().isoformat()}"
                ],
            )
            db.execute(
                "INSERT INTO community_sites (site_id, site_json, proposal_id, approved_at) "
                "VALUES (?, ?, ?, ?)",
                (site.id, site.model_dump_json(), proposal_id, _iso(now)),
            )
            db.execute(
                "UPDATE proposals SET status = 'approved', decided_at = ?, admin_note = ?, "
                "community_site_id = ? WHERE id = ?",
                (_iso(now), admin_note.strip(), site.id, proposal_id),
            )
            updated = db.execute("SELECT * FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
        return self._proposal(updated)

    def reject(self, proposal_id: int, admin_note: str = "") -> Proposal:
        """Reject a proposal, with an optional note for the proposer.

        Raises:
            KeyError: Unknown proposal.
            AccountError: Already reviewed.
        """
        with self._db() as db:
            self._pending(db, proposal_id)
            db.execute(
                "UPDATE proposals SET status = 'rejected', decided_at = ?, admin_note = ? "
                "WHERE id = ?",
                (_iso(_now()), admin_note.strip(), proposal_id),
            )
            row = db.execute("SELECT * FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
        return self._proposal(row)

    def community_sites(self) -> list[Site]:
        """Approved community sites, oldest first."""
        with self._db() as db:
            rows = db.execute(
                "SELECT site_json FROM community_sites ORDER BY approved_at"
            ).fetchall()
        return [Site.model_validate_json(row["site_json"]) for row in rows]

    def remove_community_site(self, site_id: str) -> None:
        """Take an approved site out of the catalog; ``UnknownSiteError`` if there is none."""
        with self._db() as db:
            cursor = db.execute("DELETE FROM community_sites WHERE site_id = ?", (site_id,))
        if cursor.rowcount == 0:
            raise UnknownSiteError(site_id)
