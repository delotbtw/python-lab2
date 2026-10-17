from datetime import UTC, datetime
from enum import StrEnum


def to_utc(dt: str) -> datetime:
    """
    Parse ISO 8601 string and convert it to UTC.
    Timestamp without time zone is considered to be UTC
    :param dt: timestamp string
    :return: timezone-aware datetime in UTC
    """
    timestamp = datetime.fromisoformat(dt)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    else:
        timestamp = timestamp.astimezone(UTC)
    return timestamp


class EventsLevels(StrEnum):
    """Allowed event levels"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
