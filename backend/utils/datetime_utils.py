"""DateTime utility functions.

Provides helper functions for working with datetime objects in a consistent way.
"""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Get current UTC time as a naive datetime.

    This is the recommended replacement for the deprecated datetime.utcnow().
    Returns a naive datetime (without timezone info) for compatibility with SQLite,
    which doesn't properly preserve timezone information.

    Returns:
        datetime: Current UTC time without timezone info (naive datetime)

    Example:
        >>> now = utcnow()
        >>> print(now)
        2025-10-13 12:00:00.123456
        >>> print(now.tzinfo)
        None
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
