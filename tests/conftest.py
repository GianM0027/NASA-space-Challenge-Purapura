# ABOUTME: Shared pytest setup: every test gets its own empty account store (decision D45)
# ABOUTME: Owner: Gian. Keeps tests from writing data/state/ in the working copy

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Point the account store at a throwaway folder before any module builds the app."""
    os.environ["LUNARNAV_STATE_DIR"] = tempfile.mkdtemp(prefix="lunarnav-test-state-")


@pytest.fixture(autouse=True)
def _fresh_account_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A new, empty account store for each test."""
    monkeypatch.setenv("LUNARNAV_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.delenv("LUNARNAV_ADMIN_USERS", raising=False)
