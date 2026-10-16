from dataclasses import dataclass
from datetime import datetime

from streamstats.core import EventsLevels
from streamstats.errors import InvalidEventError, InvalidTimestampError


@dataclass(eq=True, frozen=True)
class Event:
    timestamp: datetime
    level: EventsLevels
    source: str
    message: str

    def __post_init__(self) -> None:
        if self.level not in EventsLevels:
            raise InvalidEventError(message=f"invalid event level: {self.level}")
        if not isinstance(self.timestamp, datetime):
            raise InvalidTimestampError(value=str(self.timestamp))
        if not isinstance(self.source, str) or not self.source.strip():
            raise InvalidEventError(message="empty or invalid source")
        if not isinstance(self.message, str):
            raise InvalidEventError(message="invalid message")


@dataclass
class AnalysisResult:
    amount_of_events: int
    events_by_level: dict
    events_by_source: dict
    top_5_source: dict
    first_timestamp: datetime
    last_timestamp: datetime
