import csv
import json
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime

from streamstats.core import REQUIRED_FIELDS, EventsLevels
from streamstats.errors import (
    InvalidEventError,
    InvalidTimestampError,
    StreamStatsError,
    error_position,
)
from streamstats.models import Event

# Alias to future function
OnSkip = Callable[[str, int, StreamStatsError], None]


class BaseParser(ABC):
    """Base class for event parsers"""

    def __init__(self, on_skip: OnSkip | None = None) -> None:
        """
        :param on_skip: called for every skipped invalid line, None means strict mode
        :return: None
        """
        self.on_skip = on_skip

    @abstractmethod
    def parse(self, lines: Iterable[str], source_name: str) -> Iterator[Event]:
        """
        Parse lines into events one by one
        :param lines: lines of the file
        :param source_name: file name for error messages
        :return: iterator of events
        """

    def _build_event(self, record: dict) -> Event:
        """
        Build event from raw fields, timestamp is converted to UTC
        :param record: raw fields of one line
        :return: event
        """
        try:
            raw_timestamp = record["timestamp"]
            raw_level = record["level"]
            source = record["source"]
            message = record["message"]
        except KeyError as e:
            raise InvalidEventError(message=f"missing field: {e.args[0]}") from e

        try:
            # timestamp without time zone = UTC time zone
            timestamp = datetime.fromisoformat(raw_timestamp)
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
            else:
                timestamp = timestamp.astimezone(UTC)
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
        """
        Raise the error in strict mode, otherwise pass it to on_skip
        :param source_name: file name
        :param line: line number
        :param error: error of the line
        :return: None
        """
        if self.on_skip is None:
            raise error
        self.on_skip(source_name, line, error)


class JsonlParser(BaseParser):
    """Parser for JSON Lines, one JSON object per line"""

    def parse(self, lines: Iterable[str], source_name: str) -> Iterator[Event]:
        """
        Parse JSONL, empty line is an invalid line
        :param lines: lines of the file
        :param source_name: file name for error messages
        :return: iterator of events
        """
        for line_no, raw in enumerate(lines, start=1):
            try:
                with error_position(path=source_name, line=line_no):
                    try:
                        record = json.loads(raw)
                    except json.JSONDecodeError as e:
                        raise InvalidEventError(message="invalid JSON") from e

                    if not isinstance(record, dict):
                        raise InvalidEventError(message="expected JSON object")

                    event = self._build_event(record)

            except StreamStatsError as e:
                self._handle_error(source_name=source_name, line=line_no, error=e)
                continue

            yield event


class CSVParser(BaseParser):
    """Parser for CSV with header"""

    def parse(self, lines: Iterable[str], source_name: str) -> Iterator[Event]:
        """
        Parse CSV, header is checked once, missing column stops processing
        even in skip mode, empty lines are ignored by csv module
        :param lines: lines of the file
        :param source_name: file name for error messages
        :return: iterator of events
        """
        reader = csv.DictReader(lines)
        with error_position(source_name, 1):
            field_names = reader.fieldnames

            if field_names is None:
                return
            missing = REQUIRED_FIELDS - set(field_names)
            if missing:
                raise InvalidEventError(
                    message=f"missing columns: {', '.join(sorted(missing))}"
                )

        for row in reader:
            try:
                with error_position(source_name, reader.line_num):
                    if None in row:
                        raise InvalidEventError(message="too many values")
                    if None in row.values():
                        raise InvalidEventError(message="too few values")
                    event = self._build_event(record=row)
            except StreamStatsError as e:
                self._handle_error(
                    source_name=source_name, line=reader.line_num, error=e
                )
                continue

            yield event


PARSERS: dict[str, type[BaseParser]] = {"csv": CSVParser, "jsonl": JsonlParser}
