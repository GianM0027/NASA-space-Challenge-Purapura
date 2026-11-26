# ABOUTME: accounts module: optional accounts, guest sessions, per-user sites, site proposals (D45)
# ABOUTME: Owner: Gian (claimed in decision D45). SQLite file under LUNARNAV_STATE_DIR

"""Optional accounts for the public LunarNav (decision D45).

``build_account_store()`` opens the store at ``$LUNARNAV_STATE_DIR/accounts.sqlite3``
(default ``data/state``) and applies ``LUNARNAV_ADMIN_USERS`` (comma-separated usernames).
"""

from __future__ import annotations

import os
from pathlib import Path

from lunarnav.accounts.store import (
    AccountError,
    AccountLimitError,
    AccountStore,
    Proposal,
    User,
    UsernameTakenError,
)

DEFAULT_STATE_DIR = Path("data/state")


def build_account_store() -> AccountStore:
    """Open the account store configured by the environment and sync the admin list."""
    folder = Path(os.environ.get("LUNARNAV_STATE_DIR") or DEFAULT_STATE_DIR)
    store = AccountStore(folder / "accounts.sqlite3")
    store.set_admins(os.environ.get("LUNARNAV_ADMIN_USERS", "").split(","))
    store.purge_expired()
    return store


__all__ = [
    "AccountError",
    "AccountLimitError",
    "AccountStore",
    "Proposal",
    "User",
    "UsernameTakenError",
    "build_account_store",
]
