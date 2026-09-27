"""Text normalisation helpers used for matching (see docs/duplicate-detection.md §3)."""

import re

# Legal-entity suffixes that do not help tell vendors apart.
LEGAL_SUFFIXES = {
    "co", "company", "corp", "corporation", "inc", "incorporated",
    "llc", "llp", "ltd", "limited", "plc", "pvt", "private", "gmbh",
}

_NON_ALNUM = re.compile(r"[^a-z0-9\s]")
_SPACES = re.compile(r"\s+")


def normalize_vendor_name(name):
    """
    'ACME Corp.'        -> 'acme'
    'ACME Corporation'  -> 'acme'
    'Global Ltd'        -> 'global'
    """
    text = _NON_ALNUM.sub(" ", (name or "").lower())
    tokens = [token for token in _SPACES.split(text) if token]
    # Drop suffixes, but never drop every word ("Company Limited" stays "company limited").
    meaningful = [token for token in tokens if token not in LEGAL_SUFFIXES]
    return " ".join(meaningful or tokens)


def days_ago(days):
    """0 -> 'today', 1 -> '1 day ago', 5 -> '5 days ago'."""
    return "today" if days <= 0 else f"{days} day{'s' if days != 1 else ''} ago"
