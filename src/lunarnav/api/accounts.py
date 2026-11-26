# ABOUTME: API side of accounts (D45): session cookie, per-person catalog, auth and review routes
# ABOUTME: Owner: Gian. The base catalog is never written: personal sites live in the account store

"""Accounts in the REST API.

Every request gets a ``Session``: the account behind its cookie, if any. ``Session.catalog()``
is the catalog that person sees: curated sites, approved community sites and their own sites.
A visitor's first save creates a guest account and its session cookie (ends with the browser
session); registering keeps those sites, logging in moves them into the account.

Cookie: ``lunarnav_session``, HttpOnly, SameSite=Lax (no cross-site writes), Secure over HTTPS.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from lunarnav.accounts import AccountError, AccountLimitError, AccountStore, Proposal, User
from lunarnav.accounts.store import SESSION_TTL, UsernameTakenError
from lunarnav.api.site_update import DISABLED, SiteUpdater, SiteUpdateStatus, UpdateError
from lunarnav.contracts import Origin, Site, SiteCatalog
from lunarnav.contracts.errors import DuplicateSiteError, ReadOnlySiteError, UnknownSiteError

COOKIE_NAME = "lunarnav_session"


class Session:
    """The account behind one request, and the cookie to send back if it changed.

    Attributes:
        store: Account store.
        user: The account, or None for a visitor who never saved anything.
    """

    def __init__(self, store: AccountStore, request: Request, base: SiteCatalog) -> None:
        """Read the session cookie of ``request``."""
        self.store = store
        self._base = base
        self._secure = request.url.scheme == "https"
        self._token = request.cookies.get(COOKIE_NAME)
        self.user: User | None = store.user_for_token(self._token) if self._token else None
        self._cookie: tuple[str, bool] | None = None  # (token, persistent) to set
        self._clear = False

    def ensure_user(self) -> User:
        """Return the account, creating a guest account (and its cookie) when there is none."""
        if self.user is None:
            self.user = self.store.create_guest()
            self._start(self.user)
        return self.user

    def require_registered(self) -> User:
        """Return the registered account, or answer 401."""
        if self.user is None or self.user.is_guest:
            raise HTTPException(401, "Log in or create an account first.")
        return self.user

    def require_admin(self) -> User:
        """Return the admin account, or answer 401/403."""
        user = self.require_registered()
        if not user.is_admin:
            raise HTTPException(403, "Only an admin can do this.")
        return user

    def _start(self, user: User) -> None:
        if self._token:
            self.store.end_session(self._token)
        self._token = self.store.create_session(user)
        self._cookie = (self._token, not user.is_guest)
        self._clear = False

    def switch_to(self, user: User) -> None:
        """Make ``user`` the account of this browser (new session cookie)."""
        self.user = user
        self._start(user)

    def end(self) -> None:
        """Log out: forget the session and clear the cookie."""
        if self._token:
            self.store.end_session(self._token)
        self.user, self._token, self._cookie, self._clear = None, None, None, True

    def write_cookie(self, response: Response) -> None:
        """Send the new session cookie (or its removal) with ``response``, if it changed."""
        if self._clear:
            response.delete_cookie(COOKIE_NAME, path="/", samesite="lax", secure=self._secure)
        elif self._cookie is not None:
            token, persistent = self._cookie
            response.set_cookie(
                COOKIE_NAME,
                token,
                max_age=int(SESSION_TTL.total_seconds()) if persistent else None,
                path="/",
                httponly=True,
                samesite="lax",
                secure=self._secure,
            )

    def catalog(self) -> PersonalCatalog:
        """The catalog this person sees and edits."""
        return PersonalCatalog(self._base, self.store, self)


class PersonalCatalog:
    """``SiteCatalog`` of one person: shared sites plus their own.

    Shared sites are the base catalog's non-user sites and the approved community sites; user
    sites of the base catalog (one shared file, editable by anyone) are not shown any more.
    """

    def __init__(self, base: SiteCatalog, store: AccountStore, session: Session) -> None:
        """Combine the base catalog, the store and the person's session."""
        self._base = base
        self._store = store
        self._session = session

    def shared_sites(self) -> list[Site]:
        """Curated and community sites."""
        curated = [s for s in self._base.list_sites() if s.origin is not Origin.USER]
        return curated + self._store.community_sites()

    def list_sites(self) -> list[Site]:
        """Shared sites, then the person's own."""
        user = self._session.user
        return self.shared_sites() + (self._store.list_sites(user) if user else [])

    def get_site(self, site_id: str) -> Site:
        """One site by id; ``UnknownSiteError`` if this person cannot see it."""
        for site in self.list_sites():
            if site.id == site_id:
                return site
        raise UnknownSiteError(site_id)

    def _check_own(self, site_id: str) -> User:
        if any(site.id == site_id for site in self.shared_sites()):
            raise ReadOnlySiteError(f"site {site_id!r} belongs to the shared catalog")
        if self._session.user is None:
            raise UnknownSiteError(site_id)
        return self._session.user

    def add_user_site(self, site: Site) -> Site:
        """Save a personal site (creating a guest account on the first save).

        Raises:
            ValueError: The site is not a user site.
            DuplicateSiteError: The id is taken by a shared site or one of the person's own.
        """
        if site.origin is not Origin.USER:
            raise ValueError("only user sites can be saved")
        if any(shared.id == site.id for shared in self.shared_sites()):
            raise DuplicateSiteError(f"site id {site.id!r} already exists")
        return self._store.add_site(self._session.ensure_user(), site)

    def remove_user_site(self, site_id: str) -> None:
        """Delete one of the person's sites."""
        self._store.remove_site(self._check_own(site_id), site_id)

    def update_user_site(
        self, site_id: str, *, name: str | None = None, description: str | None = None
    ) -> Site:
        """Edit one of the person's sites."""
        return self._store.update_site(
            self._check_own(site_id), site_id, name=name, description=description
        )

    def rename_user_site(self, site_id: str, name: str) -> Site:
        """Rename one of the person's sites."""
        return self.update_user_site(site_id, name=name)


# --- Request and answer bodies ---------------------------------------------------------------


class Credentials(BaseModel):
    """Username and password for registering or logging in."""

    username: str = Field(max_length=64)
    password: str = Field(max_length=512)


class PasswordConfirmation(BaseModel):
    """The password again, to confirm deleting the account."""

    password: str = Field(max_length=512)


class AccountInfo(BaseModel):
    """The visitor's account as the frontend shows it (None fields for no account)."""

    username: str | None
    is_guest: bool
    is_admin: bool


class MeAnswer(BaseModel):
    """``GET /api/auth/me``: the account, or null for a visitor without one."""

    user: AccountInfo | None


class ProposalRequest(BaseModel):
    """Propose one of your own sites for the shared catalog."""

    site_id: str = Field(max_length=200)
    note: str = Field(default="", max_length=1000)


class ProposalInfo(BaseModel):
    """A proposal as the frontend shows it."""

    id: int
    username: str
    site: Site
    note: str
    status: Literal["pending", "approved", "rejected"]
    created_at: str
    decided_at: str | None
    admin_note: str
    community_site_id: str | None


class ApproveRequest(BaseModel):
    """Optional edits made by the admin when approving."""

    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    sources: list[str] = Field(default_factory=list, max_length=10)
    admin_note: str = Field(default="", max_length=1000)


class RejectRequest(BaseModel):
    """Why a proposal is rejected (shown to the proposer)."""

    admin_note: str = Field(default="", max_length=1000)


def current_session(request: Request) -> Session:
    """FastAPI dependency: the request's ``Session`` (store and base catalog from ``app.state``)."""
    return Session(request.app.state.accounts, request, request.app.state.base_catalog)


SessionDep = Annotated[Session, Depends(current_session)]


def _info(user: User | None) -> MeAnswer:
    if user is None:
        return MeAnswer(user=None)
    return MeAnswer(
        user=AccountInfo(username=user.username, is_guest=user.is_guest, is_admin=user.is_admin)
    )


def _proposal_info(proposal: Proposal) -> ProposalInfo:
    return ProposalInfo(
        id=proposal.id,
        username=proposal.username,
        site=proposal.site,
        note=proposal.note,
        status=proposal.status,
        created_at=proposal.created_at.isoformat(),
        decided_at=proposal.decided_at.isoformat() if proposal.decided_at else None,
        admin_note=proposal.admin_note,
        community_site_id=proposal.community_site_id,
    )


def _account_error(error: AccountError) -> HTTPException:
    status = 409 if isinstance(error, UsernameTakenError | AccountLimitError) else 422
    return HTTPException(status, str(error))


def build_accounts_router(store: AccountStore, updater: SiteUpdater | None = None) -> APIRouter:
    """Routes for accounts, proposals, the admin review and site updates.

    Args:
        store: Account store (the same as ``app.state.accounts``).
        updater: Site updater (decision D46); None when updating from the app is off.
    """
    router = APIRouter()

    @router.get("/api/auth/me")
    def me(session: SessionDep) -> MeAnswer:
        """The visitor's account, or null."""
        return _info(session.user)

    @router.post("/api/auth/register", status_code=201)
    def register(body: Credentials, session: SessionDep, response: Response) -> MeAnswer:
        """Create an account; a guest's saved sites are kept."""
        guest = session.user if session.user and session.user.is_guest else None
        try:
            user = store.register(body.username, body.password, guest=guest)
        except AccountError as error:
            raise _account_error(error) from error
        session.switch_to(user)
        session.write_cookie(response)
        return _info(user)

    @router.post("/api/auth/login")
    def login(body: Credentials, session: SessionDep, response: Response) -> MeAnswer:
        """Log in; a guest's saved sites move into the account."""
        user = store.authenticate(body.username, body.password)
        if user is None:
            raise HTTPException(401, "Wrong username or password.")
        if session.user is not None and session.user.is_guest:
            store.merge_guest(session.user, user)
        session.switch_to(user)
        session.write_cookie(response)
        return _info(user)

    @router.post("/api/auth/logout", status_code=204)
    def logout(session: SessionDep, response: Response) -> None:
        """Log out of this browser."""
        session.end()
        session.write_cookie(response)

    @router.post("/api/auth/delete-account", status_code=204)
    def delete_account(body: PasswordConfirmation, session: SessionDep, response: Response) -> None:
        """Delete the account and everything saved in it (password required)."""
        user = session.require_registered()
        assert user.username is not None
        if store.authenticate(user.username, body.password) is None:
            raise HTTPException(401, "Wrong password.")
        store.delete_account(user)
        session.end()
        session.write_cookie(response)

    @router.post("/api/proposals", status_code=201)
    def propose(body: ProposalRequest, session: SessionDep) -> ProposalInfo:
        """Propose one of your sites for the shared catalog."""
        user = session.require_registered()
        try:
            return _proposal_info(store.propose(user, body.site_id, body.note))
        except UnknownSiteError as error:
            raise HTTPException(404, f"unknown site id {body.site_id!r}") from error
        except AccountError as error:
            raise _account_error(error) from error

    @router.get("/api/proposals")
    def my_proposals(session: SessionDep) -> list[ProposalInfo]:
        """Your proposals with their review status, newest first."""
        if session.user is None or session.user.is_guest:
            return []
        return [_proposal_info(p) for p in store.list_proposals(session.user)]

    @router.get("/api/admin/proposals")
    def all_proposals(
        session: SessionDep, status: Literal["pending", "approved", "rejected"] | None = None
    ) -> list[ProposalInfo]:
        """Every proposal (admin), optionally only one status."""
        session.require_admin()
        return [_proposal_info(p) for p in store.list_proposals(status=status)]

    def decided(action: Callable[[], Proposal]) -> ProposalInfo:
        try:
            return _proposal_info(action())
        except KeyError as error:
            raise HTTPException(404, "unknown proposal") from error
        except AccountError as error:
            raise HTTPException(409, str(error)) from error

    @router.post("/api/admin/proposals/{proposal_id}/approve")
    def approve(proposal_id: int, body: ApproveRequest, session: SessionDep) -> ProposalInfo:
        """Approve a proposal: its site joins the shared catalog (admin)."""
        session.require_admin()
        taken = {site.id for site in session.catalog().shared_sites()}
        return decided(
            lambda: store.approve(
                proposal_id,
                taken,
                name=body.name,
                description=body.description,
                sources=body.sources,
                admin_note=body.admin_note,
            )
        )

    @router.post("/api/admin/proposals/{proposal_id}/reject")
    def reject(proposal_id: int, body: RejectRequest, session: SessionDep) -> ProposalInfo:
        """Reject a proposal, with a note for the proposer (admin)."""
        session.require_admin()
        return decided(lambda: store.reject(proposal_id, body.admin_note))

    @router.get("/api/admin/site-update")
    def site_update_status(session: SessionDep) -> SiteUpdateStatus:
        """Live version, latest version on GitHub, what changed, deploy state (admin, D46)."""
        session.require_admin()
        return updater.status() if updater is not None else DISABLED

    @router.post("/api/admin/site-update", status_code=202)
    def request_site_update(session: SessionDep) -> SiteUpdateStatus:
        """Ask the server to publish the latest version of main (admin, D46)."""
        user = session.require_admin()
        if updater is None:
            raise HTTPException(503, DISABLED.message)
        try:
            return updater.request(user.username or "admin")
        except UpdateError as error:
            raise HTTPException(409, str(error)) from error

    @router.delete("/api/admin/community-sites/{site_id}", status_code=204)
    def remove_community_site(site_id: str, session: SessionDep) -> None:
        """Take an approved site out of the shared catalog (admin)."""
        session.require_admin()
        try:
            store.remove_community_site(site_id)
        except UnknownSiteError as error:
            raise HTTPException(404, f"unknown community site {site_id!r}") from error

    return router
