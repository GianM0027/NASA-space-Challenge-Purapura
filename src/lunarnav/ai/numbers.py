# ABOUTME: Number check for LLM text (spec AI-3): every number written must come from allowed values
# ABOUTME: Owner: Gian. A number matches a value rounded as written (also as % or days)

"""Checks that an LLM-written text cites only numbers that the engine or the user produced."""

from __future__ import annotations

import re
from collections.abc import Iterable

_NUMBER = re.compile(r"(?<![\w.,])[-+]?\d+(?:[.,]\d+)?")

# A fraction may be written as a percentage, a duration in hours may be written in days.
_SCALES = (1.0, 100.0, 1.0 / 24.0)


def numbers_in(text: str) -> list[tuple[float, int]]:
    """Return every number in ``text`` with its count of decimal digits.

    A comma is read as a decimal separator (Italian and other languages write "6,5").
    """
    found = []
    for match in _NUMBER.finditer(text):
        token = match.group().replace(",", ".")
        decimals = len(token.split(".")[1]) if "." in token else 0
        found.append((float(token), decimals))
    return found


def unsupported_numbers(text: str, allowed: Iterable[float]) -> list[float]:
    """Return the numbers of ``text`` that no allowed value explains.

    A written number ``x`` with ``k`` decimals is explained by a value ``a`` when
    ``|x - a * s| <= 0.5 * 10**-k`` for a scale ``s`` in (1, 100, 1/24): the value rounded as
    written, as a percentage, or hours as days.

    Args:
        text: Text written by the LLM.
        allowed: Values it may cite.

    Returns:
        The unexplained numbers, in order of appearance (empty when the text is clean).
    """
    values = [float(a) for a in allowed]
    bad = []
    for number, decimals in numbers_in(text):
        tolerance = 0.5 * 10.0**-decimals + 1e-9
        if not any(abs(abs(number) - abs(a * s)) <= tolerance for a in values for s in _SCALES):
            bad.append(number)
    return bad
