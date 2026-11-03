from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Naive UTC 'now'. SQLite doesn't round-trip tzinfo through SQLAlchemy's
    DateTime columns, so every datetime that touches the database is naive
    UTC by convention from the moment it's created, not just after a
    round trip — otherwise comparisons against freshly-constructed
    timezone-aware datetimes raise TypeError."""
    return datetime.now(UTC).replace(tzinfo=None)
