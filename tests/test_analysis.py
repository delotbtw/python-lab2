import logging
from datetime import UTC, datetime

import pytest

from streamstats.analysis import AnalysisResult, Analyzer
from streamstats.errors import (
    CLIConfigurationError,
    InvalidEventError,
    UnsupportedFormatError,
)
from tests.helpers import CSV_HEADER, csv_line, jsonl_line, write_lines

EVENTS = [
    ("2024-01-01T10:00:00", "ERROR", "a"),
    ("2024-01-01T11:00:00", "ERROR", "a"),
    ("2024-01-01T12:00:00", "CRITICAL", "b"),
    ("2024-01-01T09:00:00", "INFO", "b"),
    ("2024-01-01T13:00:00", "DEBUG", "c"),
]


def jsonl_file(path, events=EVENTS):
    lines = [
        jsonl_line(timestamp=t, level=level, source=source)
        for t, level, source in events
    ]
    return write_lines(path=path, lines=lines)


def csv_file(path, events=EVENTS):
    lines = [
        csv_line(timestamp=t, level=level, source=source) for t, level, source in events
    ]
    return write_lines(path=path, lines=[CSV_HEADER, *lines])


def broken_file(tmp_path):
    lines = [jsonl_line(source="a"), "{broken", jsonl_line(source="b")]
    return write_lines(path=tmp_path / "bad.jsonl", lines=lines)


def test_statistics(tmp_path):
    path = jsonl_file(path=tmp_path / "a.jsonl")

    result = Analyzer(fmt="jsonl").analyze(paths=[path])

    assert result.total == 5
    assert result.total_by_level["ERROR"] == 2
    assert result.total_by_level["INFO"] == 1
    assert result.total_by_source["a"] == 2
    assert dict(result.errors_by_source) == {"a": 2, "b": 1}
    assert result.first_timestamp == datetime(
        year=2024, month=1, day=1, hour=9, tzinfo=UTC
    )
    assert result.last_timestamp == datetime(
        year=2024, month=1, day=1, hour=13, tzinfo=UTC
    )


def test_csv_and_jsonl_give_same_statistics(tmp_path):
    csv_path = csv_file(path=tmp_path / "a.csv")
    jsonl_path = jsonl_file(path=tmp_path / "a.jsonl")

    from_csv = Analyzer(fmt="csv").analyze(paths=[csv_path])
    from_jsonl = Analyzer(fmt="jsonl").analyze(paths=[jsonl_path])

    assert from_csv == from_jsonl


@pytest.mark.parametrize(argnames="fmt", argvalues=["csv", "jsonl"])
def test_empty_file(tmp_path, fmt):
    path = tmp_path / "empty"
    path.write_text(data="")

    result = Analyzer(fmt=fmt).analyze(paths=[path])

    assert result == AnalysisResult()


def test_multiple_files_are_merged(tmp_path):
    first = jsonl_file(path=tmp_path / "1.jsonl", events=EVENTS[:2])
    second = jsonl_file(path=tmp_path / "2.jsonl", events=EVENTS[2:])
    everything = jsonl_file(path=tmp_path / "all.jsonl")
    analyzer = Analyzer(fmt="jsonl")

    merged = analyzer.analyze(paths=[first, second])

    assert merged == analyzer.analyze(paths=[everything])
    assert merged == analyzer.analyze(paths=[second, first])


def test_unicode_source(tmp_path):
    path = write_lines(path=tmp_path / "u.jsonl", lines=[jsonl_line(source="сервис")])

    result = Analyzer(fmt="jsonl").analyze(paths=[path])

    assert result.total_by_source["сервис"] == 1


def test_strict_mode_raises(tmp_path):
    path = broken_file(tmp_path=tmp_path)

    with pytest.raises(expected_exception=InvalidEventError, match=r"bad\.jsonl:2"):
        Analyzer(fmt="jsonl").analyze(paths=[path])


def test_skip_mode_counts_good_lines(tmp_path, caplog):
    path = broken_file(tmp_path=tmp_path)

    with caplog.at_level(level=logging.WARNING):
        result = Analyzer(fmt="jsonl", skip_invalid=True).analyze(paths=[path])

    assert result.total == 2
    assert result.skipped == 1
    assert "bad.jsonl:2" in caplog.text


def test_skipped_are_summed_over_files(tmp_path):
    first = broken_file(tmp_path=tmp_path)
    second = write_lines(path=tmp_path / "other.jsonl", lines=["{broken", "{broken"])

    result = Analyzer(fmt="jsonl", skip_invalid=True).analyze(paths=[first, second])

    assert result.skipped == 3


def test_unsupported_format():
    with pytest.raises(expected_exception=UnsupportedFormatError):
        Analyzer(fmt="xml")


def test_missing_file(tmp_path):
    with pytest.raises(expected_exception=CLIConfigurationError):
        Analyzer(fmt="jsonl").analyze(paths=[tmp_path / "nope.jsonl"])


def test_file_not_utf8(tmp_path):
    path = tmp_path / "latin.jsonl"
    path.write_bytes(data=b"\xff\xfe\n")

    with pytest.raises(expected_exception=CLIConfigurationError):
        Analyzer(fmt="jsonl").analyze(paths=[path])


def test_input_file_is_not_modified(tmp_path):
    path = broken_file(tmp_path=tmp_path)
    before = path.read_bytes()

    Analyzer(fmt="jsonl", skip_invalid=True).analyze(paths=[path])

    assert path.read_bytes() == before
