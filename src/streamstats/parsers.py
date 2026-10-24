import csv
import json
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Iterator
from typing import Any

from streamstats.constants import REQUIRED_FIELDS
from streamstats.core import EventsLevels, to_utc
from streamstats.errors import (
    CLIConfigurationError,
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

    def _build_event(self, record: dict[str, Any]) -> Event:
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
            timestamp = to_utc(raw_timestamp)
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


PARSERS: dict[str, type[BaseParser]] = {}


def register_parser(name: str) -> Callable[[type[BaseParser]], type[BaseParser]]:
    """
    Decorator. It adds a parser class to PARSERS under the format name,
    so the format can be used in --format and in Analyzer
    :param name: format name
    :return: decorator, it returns the class unchanged
    """

    def decorator(parser_class: type[BaseParser]) -> type[BaseParser]:
        if not (
            isinstance(parser_class, type) and issubclass(parser_class, BaseParser)
        ):
            raise TypeError(f"{parser_class!r} is not a BaseParser subclass")
        if name in PARSERS:
            raise CLIConfigurationError(reason=f"parser {name!r} is already registered")
        PARSERS[name] = parser_class
        return parser_class

    return decorator


@register_parser(name="jsonl")
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
                    except (json.JSONDecodeError, RecursionError) as e:
                        raise InvalidEventError(message="invalid JSON") from e

                    if not isinstance(record, dict):
                        raise InvalidEventError(message="expected JSON object")

                    event = self._build_event(record)

            except StreamStatsError as e:
                self._handle_error(source_name=source_name, line=line_no, error=e)
                continue

            yield event


@register_parser(name="csv")
class CSVParser(BaseParser):
    """Parser for CSV with header"""

    def parse(self, lines: Iterable[str], source_name: str) -> Iterator[Event]:
        """
        Parse CSV, header is checked once, missing column stops processing
        even in skip mode, empty line is an invalid line
        :param lines: lines of the file
        :param source_name: file name for error messages
        :return: iterator of events
        """
        reader = csv.reader(lines)
        header = next(reader, None)
        if header is None:
            return
        with error_position(source_name, reader.line_num):
            missing = REQUIRED_FIELDS - set(header)
            if missing:
                raise InvalidEventError(
                    message=f"missing columns: {', '.join(sorted(missing))}"
                )

        while True:
            try:
                try:
                    row = next(reader)
                except StopIteration:
                    return
                except csv.Error as e:
                    with error_position(source_name, reader.line_num):
                        raise InvalidEventError(message=f"invalid CSV: {e}") from e
                with error_position(source_name, reader.line_num):
                    if not row:
                        raise InvalidEventError(message="empty line")
                    if len(row) > len(header):
                        raise InvalidEventError(message="too many values")
                    if len(row) < len(header):
                        raise InvalidEventError(message="too few values")
                    event = self._build_event(
                        record=dict(zip(header, row, strict=True))
                    )
            except StreamStatsError as e:
                self._handle_error(
                    source_name=source_name, line=reader.line_num, error=e
                )
                continue

            yield event
