"""Pure deterministic normalization helpers for manifest ingestion."""

import re
import string
import unicodedata

from slidelineage.errors import NormalizationError

_MISSING_TOKENS = frozenset({"", "na", "n/a", "null", "none"})
_SEPARATOR_RE = re.compile(r"[\s\-/\\]+")
_UNDERSCORE_RE = re.compile(r"_+")
_WHITESPACE_RE = re.compile(r"\s+")
_PUNCTUATION = frozenset(string.punctuation) - {"_"}


def normalize_header(value: str) -> str:
    """Return a canonical normalized header without semantic alias mapping."""

    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    normalized = _SEPARATOR_RE.sub("_", normalized)
    normalized = "".join("_" if char in _PUNCTUATION else char for char in normalized)
    normalized = _UNDERSCORE_RE.sub("_", normalized).strip("_")
    if not normalized:
        raise NormalizationError("normalized header cannot be empty")
    return normalized


def normalize_optional_text(value: str | None) -> str | None:
    """Apply minimal text cleanup while preserving case and internal characters."""

    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", value).strip()
    return normalized or None


def normalize_missing_value(value: str | None) -> str | None:
    """Map only approved missing tokens to None after trimming and case folding."""

    normalized = normalize_optional_text(value)
    if normalized is None:
        return None
    if normalized.casefold() in _MISSING_TOKENS:
        return None
    return normalized


def normalize_identifier_candidate(value: str | None) -> str | None:
    """Return conservative comparison text for future identifier-like matching."""

    normalized = normalize_missing_value(value)
    if normalized is None:
        return None
    comparison = normalized.casefold()
    return _WHITESPACE_RE.sub(" ", comparison)
