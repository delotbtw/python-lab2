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
from streamstats.models import Event
from streamstats.parsers import PARSERS

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    total: int = 0
    total_by_level: Counter = field(default_factory=Counter)
    total_by_source: Counter = field(default_factory=Counter)
    errors_by_source: Counter = field(default_factory=Counter)
    first_timestamp: datetime | None = None
    last_timestamp: datetime | None = None
    skipped: int = 0

    def add(self, event: Event) -> None:
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
    def __init__(self, fmt: str, skip_invalid: bool = False) -> None:
        if fmt not in PARSERS:
            raise UnsupportedFormatError(fmt=fmt)
        self.fmt = fmt
        self.parser_class = PARSERS[self.fmt]
        self.skip_invalid = skip_invalid

    def analyze(self, paths: Iterable[Path]) -> AnalysisResult:
        result = AnalysisResult()

        def on_skip(file: str, line: int, error: StreamStatsError) -> None:
            logger.warning("skipped invalid line: %s", error)
            result.skipped += 1

        parser = self.parser_class(on_skip if self.skip_invalid else None)
        for path in paths:
            try:
                with open(path, encoding="utf-8", newline="") as f:
                    for event in parser.parse(lines=f, source_name=str(path)):
                        result.add(event)
            except OSError as e:
                raise CLIConfigurationError(f"cannot read {path}: {e.strerror}") from e
            except UnicodeDecodeError as e:
                raise CLIConfigurationError(reason="file is not utf-8 encoding") from e

        return result
