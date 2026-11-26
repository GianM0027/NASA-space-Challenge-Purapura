# ABOUTME: Tests of the account store (D45): accounts, sessions, guests, personal sites, proposals
# ABOUTME: Owner: Gian. Each test uses its own SQLite file under pytest's tmp_path

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from lunarnav.accounts import AccountError, AccountLimitError, AccountStore, UsernameTakenError
from lunarnav.accounts import store as store_module
from lunarnav.accounts.passwords import hash_password, verify_password
from lunarnav.contracts import GeoPoint, Origin, Site
from lunarnav.contracts.errors import DuplicateSiteError, UnknownSiteError

PASSWORD = "correct horse battery"


def _site(slug: str = "my-crater", lat: float = -85.0) -> Site:
    return Site(
        id=f"user-{slug}",
        name=slug.replace("-", " ").title(),
        location=GeoPoint(lat_deg=lat, lon_deg=30.0),
        origin=Origin.USER,
        status="custom",
        description="A quiet rim.",
    )


@pytest.fixture
def store(tmp_path: Path) -> AccountStore:
    return AccountStore(tmp_path / "accounts.sqlite3")


def test_password_hash_round_trip_and_salt() -> None:
    first, second = hash_password(PASSWORD), hash_password(PASSWORD)
    assert first != second  # random salt
    assert verify_password(PASSWORD, first)
    assert not verify_password("wrong password", first)
    assert not verify_password(PASSWORD, "not-a-hash")
    assert PASSWORD not in first


def test_register_and_authenticate(store: AccountStore) -> None:
    user = store.register("Gian", PASSWORD)
    assert (user.username, user.is_guest, user.is_admin) == ("Gian", False, False)
    assert store.authenticate("gian", PASSWORD) == user  # usernames are case-insensitive
    assert store.authenticate("Gian", "wrong password") is None
    assert store.authenticate("nobody", PASSWORD) is None


@pytest.mark.parametrize("name", ["ab", "with space", "-dash-first", "x" * 33, "è-accent"])
def test_invalid_usernames_are_rejected(store: AccountStore, name: str) -> None:
    with pytest.raises(AccountError, match="Usernames"):
        store.register(name, PASSWORD)


def test_short_password_and_taken_username(store: AccountStore) -> None:
    with pytest.raises(AccountError, match="at least 8"):
        store.register("gian", "short")
    store.register("gian", PASSWORD)
    with pytest.raises(UsernameTakenError):
        store.register("GIAN", PASSWORD)


def test_sessions_expire_and_end(store: AccountStore, monkeypatch: pytest.MonkeyPatch) -> None:
    user = store.register("gian", PASSWORD)
    token = store.create_session(user)
    assert store.user_for_token(token) == user
    assert store.user_for_token("forged") is None
    later = datetime.now(UTC) + store_module.SESSION_TTL + timedelta(minutes=1)
    monkeypatch.setattr(store_module, "_now", lambda: later)
    assert store.user_for_token(token) is None
    monkeypatch.undo()
    token = store.create_session(user)
    store.end_session(token)
    assert store.user_for_token(token) is None


def test_session_tokens_are_not_stored_in_clear(store: AccountStore, tmp_path: Path) -> None:
    token = store.create_session(store.register("gian", PASSWORD))
    assert token.encode() not in (tmp_path / "accounts.sqlite3").read_bytes()


def test_registering_a_guest_keeps_its_sites(store: AccountStore) -> None:
    guest = store.create_guest()
    store.add_site(guest, _site())
    user = store.register("gian", PASSWORD, guest=guest)
    assert user.id == guest.id and not user.is_guest
    assert [s.id for s in store.list_sites(user)] == ["user-my-crater"]


def test_logging_in_moves_guest_sites_without_overwriting(store: AccountStore) -> None:
    user = store.register("gian", PASSWORD)
    store.add_site(user, _site("shared-name", lat=-80))
    guest = store.create_guest()
    store.add_site(guest, _site("shared-name", lat=-70))  # same id: the account's copy wins
    store.add_site(guest, _site("new-one"))
    assert store.merge_guest(guest, user) == 1
    sites = {s.id: s for s in store.list_sites(user)}
    assert set(sites) == {"user-shared-name", "user-new-one"}
    assert sites["user-shared-name"].location.lat_deg == -80


def test_personal_sites_are_private(store: AccountStore) -> None:
    alice, bob = store.register("alice", PASSWORD), store.register("bob", PASSWORD)
    store.add_site(alice, _site())
    assert store.list_sites(bob) == []
    with pytest.raises(UnknownSiteError):
        store.remove_site(bob, "user-my-crater")
    store.add_site(bob, _site())  # the same id is fine in another account
    with pytest.raises(DuplicateSiteError):
        store.add_site(bob, _site())


def test_update_and_remove_site(store: AccountStore) -> None:
    user = store.register("gian", PASSWORD)
    store.add_site(user, _site())
    updated = store.update_site(user, "user-my-crater", name=" New name ", description="")
    assert (updated.name, updated.description, updated.id) == ("New name", "", "user-my-crater")
    with pytest.raises(ValueError, match="blank"):
        store.update_site(user, "user-my-crater", name="  ")
    store.remove_site(user, "user-my-crater")
    assert store.list_sites(user) == []


def test_site_limit(store: AccountStore, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store_module, "MAX_SITES_PER_ACCOUNT", 2)
    user = store.register("gian", PASSWORD)
    store.add_site(user, _site("a"))
    store.add_site(user, _site("b"))
    with pytest.raises(AccountLimitError):
        store.add_site(user, _site("c"))


def test_purge_forgets_guests_without_sessions(
    store: AccountStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    guest = store.create_guest()
    token = store.create_session(guest)
    store.add_site(guest, _site())
    later = datetime.now(UTC) + store_module.GUEST_TTL + timedelta(minutes=1)
    monkeypatch.setattr(store_module, "_now", lambda: later)
    store.purge_expired()
    assert store.user_for_token(token) is None
    assert store.list_sites(guest) == []


def test_delete_account_removes_its_data(store: AccountStore) -> None:
    user = store.register("gian", PASSWORD)
    store.add_site(user, _site())
    store.propose(user, "user-my-crater", "Nice")
    token = store.create_session(user)
    store.delete_account(user)
    assert store.user_for_token(token) is None
    assert store.authenticate("gian", PASSWORD) is None
    assert store.list_proposals() == []  # pending proposals go with the account


def test_proposal_flow_approve(store: AccountStore) -> None:
    user = store.register("gian", PASSWORD)
    store.add_site(user, _site())
    proposal = store.propose(user, "user-my-crater", "Flat and lit.")
    assert proposal.status == "pending" and proposal.username == "gian"
    approved = store.approve(
        proposal.id, {"community-my-crater"}, name="Crater rim", admin_note="Thanks!"
    )
    assert approved.status == "approved" and approved.admin_note == "Thanks!"
    assert approved.community_site_id == "community-my-crater-2"  # the taken id is avoided
    (site,) = store.community_sites()
    assert (site.id, site.name, site.origin, site.status) == (
        "community-my-crater-2",
        "Crater rim",
        Origin.OTHER,
        "candidate",
    )
    assert site.sources and "proposal" in site.sources[0]  # every catalog site needs a source
    with pytest.raises(AccountError, match="already reviewed"):
        store.reject(proposal.id)


def test_proposal_flow_reject_and_limits(
    store: AccountStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = store.register("gian", PASSWORD)
    for slug in ("a", "b", "c"):
        store.add_site(user, _site(slug))
    first = store.propose(user, "user-a", "")
    with pytest.raises(AccountError, match="already waiting"):
        store.propose(user, "user-a", "")
    monkeypatch.setattr(store_module, "MAX_PENDING_PROPOSALS", 2)
    store.propose(user, "user-b", "")
    with pytest.raises(AccountLimitError):
        store.propose(user, "user-c", "")
    rejected = store.reject(first.id, "Already in the catalog.")
    assert rejected.status == "rejected"
    assert [p.status for p in store.list_proposals(user)] == ["pending", "rejected"]
    with pytest.raises(KeyError):
        store.reject(999)


def test_guests_cannot_propose(store: AccountStore) -> None:
    guest = store.create_guest()
    store.add_site(guest, _site())
    with pytest.raises(AccountError, match="Create an account"):
        store.propose(guest, "user-my-crater", "")


def test_admin_list_and_community_removal(store: AccountStore) -> None:
    store.register("gian", PASSWORD)
    store.register("friend", PASSWORD)
    store.set_admins(["GIAN"])
    assert store.authenticate("gian", PASSWORD).is_admin  # type: ignore[union-attr]
    assert not store.authenticate("friend", PASSWORD).is_admin  # type: ignore[union-attr]
    with pytest.raises(UnknownSiteError):
        store.remove_community_site("community-nothing")


def test_admin_named_before_registering_becomes_admin_on_register(store: AccountStore) -> None:
    store.set_admins(["gian"])
    assert store.register("Gian", PASSWORD).is_admin
    assert not store.register("friend", PASSWORD).is_admin
