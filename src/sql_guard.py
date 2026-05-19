"""SQL safety validation for LLM-generated queries.

Layered defenses (in order):
  1. Strip code fences/markdown wrappers around the SQL.
  2. Must be a single statement (no semicolons except a trailing one).
  3. Must start with SELECT or WITH.
  4. Must not contain DML/DDL/admin keywords as standalone tokens.
  5. Must not contain block- or line-comment markers (anti-injection).

The DB-side defense (readonly role + statement_timeout) is the *real* moat;
this layer is for fast feedback and clearer error messages.
"""
from __future__ import annotations

import re

_FORBIDDEN_TOKENS = {
    "insert", "update", "delete", "drop", "alter", "truncate", "create",
    "grant", "revoke", "copy", "vacuum", "analyze", "reindex", "cluster",
    "comment", "execute", "call", "do", "begin", "commit", "rollback",
    "savepoint", "set", "reset", "listen", "notify", "load", "lock",
    "refresh", "import", "merge",
}

_CODE_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_WORD = re.compile(r"\b([a-z_]+)\b")


class SQLValidationError(ValueError):
    """Raised when an LLM-generated SQL string fails safety checks."""


def extract_sql(text: str) -> str:
    """Pull SQL out of a markdown code fence if present, else return trimmed text."""
    m = _CODE_FENCE.search(text)
    candidate = m.group(1) if m else text
    return candidate.strip().rstrip(";").strip()


def validate_sql(sql: str) -> str:
    """Raise SQLValidationError if the SQL is unsafe; otherwise return it normalized."""
    s = sql.strip().rstrip(";").strip()
    if not s:
        raise SQLValidationError("Empty SQL.")

    # Reject multiple statements
    if ";" in s:
        raise SQLValidationError("Multiple statements are not allowed.")

    # Reject SQL comments (injection vector)
    if "--" in s or "/*" in s or "*/" in s:
        raise SQLValidationError("SQL comments are not allowed.")

    lower = s.lower()
    first_word_match = re.match(r"\s*([a-z]+)", lower)
    if not first_word_match:
        raise SQLValidationError("Could not parse SQL.")
    first = first_word_match.group(1)
    if first not in {"select", "with"}:
        raise SQLValidationError(f"Only SELECT/WITH queries allowed (got: {first.upper()}).")

    # Check for forbidden tokens as whole words
    tokens = set(_WORD.findall(lower))
    bad = tokens & _FORBIDDEN_TOKENS
    if bad:
        raise SQLValidationError(f"Forbidden keyword(s): {', '.join(sorted(bad))}")

    return s
