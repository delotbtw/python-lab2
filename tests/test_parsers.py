from datetime import UTC, datetime

import pytest

from streamstats.errors import InvalidEventError, InvalidTimestampError
from streamstats.parsers import CSVParser, JsonlParser
from tests.helpers import CSV_HEADER, csv_line, jsonl_line

TEN_AM_UTC = datetime(year=2024, month=1, day=1, hour=10, tzinfo=UTC)


def test_jsonl_event():
    lines = [jsonl_line(level="ERROR", source="db")]

    (event,) = JsonlParser().parse(lines=lines, source_name="f")

    assert event.level == "ERROR"
    assert event.source == "db"
    assert event.timestamp == TEN_AM_UTC


def test_csv_event():
    lines = [CSV_HEADER, csv_line(level="ERROR")]

    (event,) = CSVParser().parse(lines=lines, source_name="f")

    assert event.level == "ERROR"
    assert event.timestamp == TEN_AM_UTC


def test_csv_and_jsonl_give_same_events():
    csv_lines = [
        CSV_HEADER,
        csv_line(source="a"),
        csv_line(level="ERROR", source="б"),
    ]
    jsonl_lines = [jsonl_line(source="a"), jsonl_line(level="ERROR", source="б")]

    from_csv = list(CSVParser().parse(lines=csv_lines, source_name="f"))
    from_jsonl = list(JsonlParser().parse(lines=jsonl_lines, source_name="f"))

    assert from_csv == from_jsonl


def test_timestamp_is_converted_to_utc():
    lines = [
        jsonl_line(timestamp="2024-01-01T10:00:00"),
        jsonl_line(timestamp="2024-01-01T10:00:00Z"),
        jsonl_line(timestamp="2024-01-01T13:00:00+03:00"),
    ]

    events = JsonlParser().parse(lines=lines, source_name="f")

    assert {e.timestamp for e in events} == {TEN_AM_UTC}


def test_unicode():
    jsonl_lines = [jsonl_line(source="сервис", message="привет")]
    csv_lines = [CSV_HEADER, csv_line(source="сервис", message="привет")]

    jsonl_events = JsonlParser().parse(lines=jsonl_lines, source_name="f")
    csv_events = CSVParser().parse(lines=csv_lines, source_name="f")

    assert next(jsonl_events).message == "привет"
    assert next(csv_events).source == "сервис"


def test_csv_quoted_comma():
    lines = [CSV_HEADER, '2024-01-01T10:00:00,INFO,auth,"привет, мир"']

    (event,) = CSVParser().parse(lines=lines, source_name="f")

    assert event.message == "привет, мир"


def test_empty_input():
    jsonl_events = JsonlParser().parse(lines=[], source_name="f")
    csv_events = CSVParser().parse(lines=[], source_name="f")
    csv_header_only = CSVParser().parse(lines=[CSV_HEADER], source_name="f")

    assert list(jsonl_events) == []
    assert list(csv_events) == []
    assert list(csv_header_only) == []


def test_parser_reads_lazily():
    read = []

    def lines():
        for i in range(1000):
            read.append(i)
            yield jsonl_line()

    next(JsonlParser().parse(lines=lines(), source_name="f"))

    assert len(read) == 1


def test_invalid_json_reports_line_7():
    lines = [jsonl_line()] * 6 + ["{broken"]

    with pytest.raises(
        expected_exception=InvalidEventError, match=r"data\.jsonl:7: invalid JSON"
    ):
        list(JsonlParser().parse(lines=lines, source_name="data.jsonl"))


@pytest.mark.parametrize(
    argnames="line",
    argvalues=[
        "[1, 2]",
        '{"timestamp": "2024-01-01T10:00:00"}',
        jsonl_line(level="TRACE"),
        jsonl_line(source=""),
        jsonl_line(source=None),
        jsonl_line(message=123),
    ],
)
def test_invalid_jsonl_event(line):
    lines = [jsonl_line(), line]

    with pytest.raises(expected_exception=InvalidEventError, match=r"data\.jsonl:2:"):
        list(JsonlParser().parse(lines=lines, source_name="data.jsonl"))


def test_invalid_timestamp_reports_value_and_line():
    lines = [jsonl_line(), jsonl_line(timestamp="not-a-date")]

    with pytest.raises(
        expected_exception=InvalidTimestampError,
        match=r"data\.jsonl:2: invalid timestamp: not-a-date",
    ):
        list(JsonlParser().parse(lines=lines, source_name="data.jsonl"))


def test_csv_invalid_timestamp_reports_value_and_line():
    lines = [CSV_HEADER, csv_line(), csv_line(timestamp="not-a-date")]

    with pytest.raises(
        expected_exception=InvalidTimestampError,
        match=r"data\.csv:3: invalid timestamp: not-a-date",
    ):
        list(CSVParser().parse(lines=lines, source_name="data.csv"))


def test_csv_missing_column():
    lines = ["timestamp,level,source"]

    with pytest.raises(
        expected_exception=InvalidEventError, match="missing columns: message"
    ):
        list(CSVParser().parse(lines=lines, source_name="f"))


def test_csv_missing_column_is_not_skipped():
    parser = CSVParser(on_skip=lambda file, line, error: None)

    with pytest.raises(expected_exception=InvalidEventError):
        list(parser.parse(lines=["timestamp,level"], source_name="f"))


def test_csv_wrong_number_of_values():
    few = [CSV_HEADER, "2024-01-01T10:00:00,INFO,auth"]
    many = [CSV_HEADER, csv_line() + ",extra"]

    with pytest.raises(
        expected_exception=InvalidEventError, match=r"data\.csv:2: too few"
    ):
        list(CSVParser().parse(lines=few, source_name="data.csv"))
    with pytest.raises(
        expected_exception=InvalidEventError, match=r"data\.csv:2: too many"
    ):
        list(CSVParser().parse(lines=many, source_name="data.csv"))


def test_strict_mode_stops_on_first_bad_line():
    lines = [jsonl_line(source="a"), "{broken", jsonl_line(source="b")]
    events = JsonlParser().parse(lines=lines, source_name="data.jsonl")

    assert next(events).source == "a"
    with pytest.raises(expected_exception=InvalidEventError, match=r"data\.jsonl:2"):
        next(events)


def test_skip_mode_keeps_good_lines():
    skipped = []
    parser = JsonlParser(on_skip=lambda file, line, error: skipped.append(line))
    lines = [jsonl_line(source="a"), "{broken", jsonl_line(source="b"), "{broken"]

    events = list(parser.parse(lines=lines, source_name="f"))

    assert [e.source for e in events] == ["a", "b"]
    assert skipped == [2, 4]


def test_skip_mode_csv():
    skipped = []
    parser = CSVParser(on_skip=lambda file, line, error: skipped.append(line))
    lines = [CSV_HEADER, csv_line(), "2024-01-01T10:00:00,INFO,auth", csv_line()]

    events = list(parser.parse(lines=lines, source_name="f"))

    assert len(events) == 2
    assert skipped == [3]


def test_csv_empty_line_is_invalid():
    lines = [CSV_HEADER, csv_line(), "", csv_line()]

    with pytest.raises(
        expected_exception=InvalidEventError, match=r"data\.csv:3: empty line"
    ):
        list(CSVParser().parse(lines=lines, source_name="data.csv"))


def test_csv_empty_line_in_skip_mode():
    skipped = []
    parser = CSVParser(on_skip=lambda file, line, error: skipped.append(line))
    lines = [CSV_HEADER, csv_line(), "", csv_line()]

    events = list(parser.parse(lines=lines, source_name="f"))

    assert len(events) == 2
    assert skipped == [3]


def test_jsonl_empty_line_is_invalid_too():
    lines = [jsonl_line(), "", jsonl_line()]

    with pytest.raises(
        expected_exception=InvalidEventError, match=r"data\.jsonl:2: invalid JSON"
    ):
        list(JsonlParser().parse(lines=lines, source_name="data.jsonl"))


def test_timestamp_out_of_range_is_invalid_timestamp():
    lines = [jsonl_line(timestamp="0001-01-01T00:00:00+05:00")]

    with pytest.raises(
        expected_exception=InvalidTimestampError, match=r"data\.jsonl:1:"
    ):
        list(JsonlParser().parse(lines=lines, source_name="data.jsonl"))


def test_deeply_nested_json_is_invalid_json():
    lines = ["[" * 100_000 + "]" * 100_000]

    with pytest.raises(
        expected_exception=InvalidEventError, match=r"data\.jsonl:1: invalid JSON"
    ):
        list(JsonlParser().parse(lines=lines, source_name="data.jsonl"))


def test_csv_field_over_the_limit_is_invalid_line():
    lines = [CSV_HEADER, csv_line(), csv_line(message="x" * 200_000), csv_line()]

    with pytest.raises(
        expected_exception=InvalidEventError, match=r"data\.csv:3: invalid CSV"
    ):
        list(CSVParser().parse(lines=lines, source_name="data.csv"))


def test_csv_field_over_the_limit_in_skip_mode():
    skipped = []
    parser = CSVParser(on_skip=lambda file, line, error: skipped.append(line))
    lines = [CSV_HEADER, csv_line(), csv_line(message="x" * 200_000), csv_line()]

    events = list(parser.parse(lines=lines, source_name="f"))

    assert len(events) == 2
    assert skipped == [3]
