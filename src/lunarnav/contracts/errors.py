# ABOUTME: Errors shared by module implementations and the API (mapped to HTTP status codes)
# ABOUTME: Owner: Gian. Each subclasses the builtin the ports used before, so old callers still work

"""Contract errors.

Implementations raise these; ``lunarnav.api`` maps them to HTTP status codes. Each one subclasses
the builtin exception the ports used before it existed, so code that catches ``KeyError`` or
``ValueError`` keeps working.
"""

from __future__ import annotations


class UnknownSiteError(KeyError):
    """No site has the requested id (HTTP 404)."""


class DuplicateSiteError(ValueError):
    """A site with the same id already exists (HTTP 409)."""


class ReadOnlySiteError(PermissionError):
    """The site is curated (``origin != "user"``) and cannot be renamed or removed (HTTP 403)."""
