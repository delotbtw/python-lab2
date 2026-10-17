from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime

from streamstats.core import EventsLevels
from streamstats.models import Event


@dataclass(frozen=True)
class EventsFilters:
    """Lazy filters of events, None means that the condition is not set"""

    levels: frozenset[EventsLevels] | None = None
    sources: frozenset[str] | None = None
    since: datetime | None = None
    until: datetime | None = None

    def _matches(self, event: Event) -> bool:
        """
        Check event by all set conditions, since is included, until is not
        :param event: event to check
        :return: True if event passes all conditions
        """
        if self.levels is not None and event.level not in self.levels:
            return False
        if self.sources is not None and event.source not in self.sources:
            return False
        if self.since is not None and event.timestamp < self.since:
            return False

        return self.until is None or event.timestamp < self.until

    def apply(self, events: Iterable[Event]) -> Iterator[Event]:
        """
        Pass events one by one, events that do not match are dropped
        :param events: events to filter
        :return: iterator of matching events
        """
        for event in events:
            if self._matches(event=event):
                yield event
