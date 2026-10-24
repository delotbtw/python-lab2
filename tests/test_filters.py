from datetime import UTC, datetime, timedelta, timezone

import pytest

from streamstats.core import EventsLevels, to_utc
from streamstats.filters import EventsFilters
from streamstats.models import Event


def make_event(hour=10, level="INFO", source="a"):
    return Event(
        timestamp=datetime(year=2024, month=1, day=1, hour=hour, tzinfo=UTC),
        level=EventsLevels(value=level),
        source=source,
        message="m",
    )


def hour_utc(hour):
    return datetime(year=2024, month=1, day=1, hour=hour, tzinfo=UTC)


def hours(events):
    return [event.timestamp.hour for event in events]


EVENTS = [
    make_event(hour=9, level="INFO", source="a"),
    make_event(hour=10, level="ERROR", source="a"),
    make_event(hour=11, level="CRITICAL", source="b"),
    make_event(hour=12, level="DEBUG", source="b"),
]


def test_empty_filter_passes_everything():
    assert hours(EventsFilters().apply(events=EVENTS)) == [9, 10, 11, 12]


def test_filter_by_level():
    event_filter = EventsFilters(
        levels=frozenset({EventsLevels.ERROR, EventsLevels.CRITICAL})
    )

    assert hours(event_filter.apply(events=EVENTS)) == [10, 11]


def test_filter_by_source():
    event_filter = EventsFilters(sources=frozenset({"b"}))

    assert hours(event_filter.apply(events=EVENTS)) == [11, 12]


def test_since_is_included_and_until_is_not():
    event_filter = EventsFilters(since=hour_utc(10), until=hour_utc(12))

    assert hours(event_filter.apply(events=EVENTS)) == [10, 11]


def test_only_since():
    event_filter = EventsFilters(since=hour_utc(11))

    assert hours(event_filter.apply(events=EVENTS)) == [11, 12]


def test_only_until():
    event_filter = EventsFilters(until=hour_utc(10))

    assert hours(event_filter.apply(events=EVENTS)) == [9]


def test_time_zone_of_filter_is_taken_into_account():
    plus_three = timezone(offset=timedelta(hours=3))
    event_filter = EventsFilters(
        since=datetime(year=2024, month=1, day=1, hour=13, tzinfo=plus_three)
    )

    assert hours(event_filter.apply(events=EVENTS)) == [10, 11, 12]


def test_conditions_are_combined_with_and():
    event_filter = EventsFilters(
        levels=frozenset({EventsLevels.ERROR, EventsLevels.CRITICAL}),
        sources=frozenset({"b"}),
        since=hour_utc(10),
    )

    assert hours(event_filter.apply(events=EVENTS)) == [11]


def test_empty_set_passes_nothing_but_none_passes_everything():
    nothing = EventsFilters(levels=frozenset())
    everything = EventsFilters(levels=None)

    assert hours(nothing.apply(events=EVENTS)) == []
    assert hours(everything.apply(events=EVENTS)) == [9, 10, 11, 12]


def test_filter_is_lazy():
    read = []

    def events():
        for i in range(1000):
            read.append(i)
            yield make_event()

    next(EventsFilters(sources=frozenset({"a"})).apply(events=events()))

    assert len(read) == 1


def test_to_utc_without_time_zone_is_utc():
    assert to_utc(dt="2024-01-01T10:00:00") == hour_utc(10)


def test_to_utc_converts_offset():
    converted = to_utc(dt="2024-01-01T13:00:00+03:00")

    assert converted == hour_utc(10)
    assert converted.utcoffset() == timedelta(0)


def test_to_utc_z_suffix():
    assert to_utc(dt="2024-01-01T10:00:00Z") == hour_utc(10)


def test_to_utc_invalid_string():
    with pytest.raises(expected_exception=ValueError):
        to_utc(dt="not-a-date")


def test_to_utc_out_of_range():
    with pytest.raises(expected_exception=ValueError, match="out of range"):
        to_utc(dt="0001-01-01T00:00:00+05:00")
