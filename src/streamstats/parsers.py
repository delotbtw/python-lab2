from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Iterator
from datetime import datetime

from src.streamstats.core import EventsLevels
from src.streamstats.errors import (
    InvalidEventError,
    InvalidTimestampError,
    StreamStatsError,
)
from src.streamstats.models import Event

# Alias to future function
OnSkip = Callable[[str, int, StreamStatsError], None]


class BaseParser(ABC):
    def __init__(self, on_skip: OnSkip | None = None) -> None:
        self.on_skip = on_skip

    @abstractmethod
    def parse(lines: Iterable[str], source_name: str) -> Iterator[Event]: ...

    def _build_event(self, record: dict) -> Event:
        try:
            raw_timestamp = record["timestamp"]
            raw_level = record["level"]
            source = record["source"]
            message = record["message"]
        except KeyError as e:
            raise InvalidEventError(message=f"missing field: {e.args[0]}")

        try:
            timestamp = datetime.fromisoformat(raw_timestamp)
        except (ValueError, TypeError) as e:
            raise InvalidTimestampError(value=str(raw_timestamp)) from e

        try:
            level = EventsLevels(raw_level)
        except ValueError as e:
            raise InvalidEventError(message=f"invalid event level: {raw_level}") from e

        return Event(timestamp=timestamp, level=level, source=source, message=message)

    def _handle_error(
        self, source_name: str, line: int, error: StreamStatsError
    ) -> None:
        if self.on_skip is None:
            raise error
        self.on_skip(source_name, line, error)
