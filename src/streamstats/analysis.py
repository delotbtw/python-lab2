import logging
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from streamstats.core import EventsLevels
from streamstats.errors import (
    CLIConfigurationError,
    StreamStatsError,
    UnsupportedFormatError,
)
from streamstats.filters import EventsFilters
from streamstats.models import Event
from streamstats.parsers import PARSERS

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Statistics of all processed files"""

    total: int = 0
    total_by_level: Counter[str] = field(default_factory=Counter)
    total_by_source: Counter[str] = field(default_factory=Counter)
    errors_by_source: Counter[str] = field(default_factory=Counter)
    first_timestamp: datetime | None = None
    last_timestamp: datetime | None = None
    skipped: int = 0

    def add(self, event: Event) -> None:
        """
        Count one event, the event itself is not stored
        :param event: parsed event
        :return: None
        """
        self.total += 1
        self.total_by_level[event.level] += 1
        self.total_by_source[event.source] += 1
        if event.level in (EventsLevels.CRITICAL, EventsLevels.ERROR):
            self.errors_by_source[event.source] += 1
        if self.first_timestamp is None or self.first_timestamp > event.timestamp:
            self.first_timestamp = event.timestamp
        if self.last_timestamp is None or self.last_timestamp < event.timestamp:
            self.last_timestamp = event.timestamp


class Analyzer:
    """Reads files line by line and collects statistics"""

    def __init__(
        self,
        fmt: str,
        skip_invalid: bool = False,
        event_filter: EventsFilters | None = None,
    ) -> None:
        """
        :param fmt: input format, csv or jsonl
        :param skip_invalid: skip invalid lines with a warning instead of stopping
        :param event_filter: filters of events, all events pass if None
        :return: None
        """
        if fmt not in PARSERS:
            raise UnsupportedFormatError(fmt=fmt)
        self.fmt = fmt
        self.parser_class = PARSERS[self.fmt]
        self.skip_invalid = skip_invalid
        self.event_filters = event_filter or EventsFilters()

    def analyze(self, paths: Iterable[Path]) -> AnalysisResult:
        """
        Analyze files one by one into a single result
        :param paths: input files
        :return: statistics of all files
        """
        result = AnalysisResult()

        def on_skip(file: str, line: int, error: StreamStatsError) -> None:
            """Log skipped line and count it"""
            logger.warning("skipped invalid line: %s", error)
            result.skipped += 1

        parser = self.parser_class(on_skip if self.skip_invalid else None)
        for path in paths:
            try:
                with open(path, encoding="utf-8-sig", newline="") as f:
                    for event in self.event_filters.apply(
                        events=parser.parse(lines=f, source_name=str(path))
                    ):
                        result.add(event)
            except OSError as e:
                raise CLIConfigurationError(f"cannot read {path}: {e.strerror}") from e
            except UnicodeDecodeError as e:
                raise CLIConfigurationError(reason="file is not utf-8 encoding") from e

        return result
