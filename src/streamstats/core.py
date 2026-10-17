from enum import StrEnum

REQUIRED_FIELDS = {"timestamp", "level", "source", "message"}


class EventsLevels(StrEnum):
    """Allowed event levels"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
