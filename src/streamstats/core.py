from datetime import UTC, datetime
from enum import StrEnum


def to_utc(dt: str) -> datetime:
    """
    Parse ISO 8601 string and convert it to UTC.
    Timestamp without time zone is considered to be UTC
    :param dt: timestamp string
    :return: timezone-aware datetime in UTC
    """
    try:
        timestamp = datetime.fromisoformat(dt)
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC)
    except OverflowError as e:
        raise ValueError(f"timestamp is out of range: {dt}") from e


class EventsLevels(StrEnum):
    """Allowed event levels"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
