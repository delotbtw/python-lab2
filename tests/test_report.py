import csv
import io
import json
from collections import Counter
from datetime import UTC, datetime

import pytest

from streamstats.analysis import AnalysisResult
from streamstats.constants import TOP_N
from streamstats.core import EventsLevels
from streamstats.errors import UnsupportedFormatError
from streamstats.models import Event
from streamstats.report import Report, get_top_n


def make_result(*items):
    result = AnalysisResult()
    for level, source in items:
        event = Event(
            timestamp=datetime(year=2024, month=1, day=1, tzinfo=UTC),
            level=EventsLevels(value=level),
            source=source,
            message="m",
        )
        result.add(event=event)
    return result


def test_top_sorted_by_count_then_name():
    errors = Counter(z=3, b=1, a=1, c=2)

    top = get_top_n(errors_by_source=errors, n=10)

    assert [item["source"] for item in top] == ["z", "c", "a", "b"]
    assert top[0] == {"source": "z", "count": 3}


def test_top_ties_do_not_depend_on_order():
    forward = Counter()
    backward = Counter()
    for name in "abcd":
        forward[name] += 1
    for name in "dcba":
        backward[name] += 1

    assert get_top_n(errors_by_source=forward, n=3) == get_top_n(
        errors_by_source=backward, n=3
    )


def test_top_n_is_configurable():
    result = make_result(*[("ERROR", name) for name in "abcdefg"])

    default = Report(result=result).to_dict()["top_error_sources"]
    three = Report(result=result, top_n=3).to_dict()["top_error_sources"]

    assert len(default) == TOP_N
    assert len(three) == 3


def test_top_contains_only_errors():
    result = make_result(("INFO", "i"), ("WARNING", "w"), ("ERROR", "e"))

    top = Report(result=result).to_dict()["top_error_sources"]

    assert top == [{"source": "e", "count": 1}]


def test_empty_report():
    report = Report(result=AnalysisResult()).to_dict()

    assert report == {
        "total": 0,
        "skipped": 0,
        "by_level": {level.value: 0 for level in EventsLevels},
        "by_source": {},
        "top_error_sources": [],
        "first_timestamp": None,
        "last_timestamp": None,
    }


def test_report_content():
    result = make_result(("ERROR", "a"), ("INFO", "b"), ("INFO", "b"))
    result.skipped = 4

    report = Report(result=result).to_dict()

    assert report["total"] == 3
    assert report["skipped"] == 4
    assert report["by_level"]["INFO"] == 2
    assert report["by_source"] == {"a": 1, "b": 2}
    assert report["first_timestamp"] == "2024-01-01T00:00:00+00:00"


def test_cyrillic_is_not_escaped(tmp_path):
    report = Report(result=make_result(("ERROR", "сервис")))
    path = tmp_path / "report.json"

    report.write(path=path)

    text = path.read_text(encoding="utf-8")
    assert "сервис" in text
    assert json.loads(s=text)["by_source"] == {"сервис": 1}


def read_csv(text):
    return list(csv.reader(io.StringIO(initial_value=text)))


def test_csv_report_content():
    result = make_result(("ERROR", "a"), ("INFO", "b"), ("INFO", "b"))
    result.skipped = 4

    rows = read_csv(Report(result=result).to_csv())

    assert rows[0] == ["section", "key", "value"]
    assert ["total", "", "3"] in rows
    assert ["skipped", "", "4"] in rows
    assert ["level", "INFO", "2"] in rows
    assert ["level", "DEBUG", "0"] in rows
    assert ["source", "b", "2"] in rows
    assert ["top_error_source", "a", "1"] in rows
    assert ["first_timestamp", "", "2024-01-01T00:00:00+00:00"] in rows


def test_csv_report_has_same_data_as_json_report():
    result = make_result(("ERROR", "a"), ("CRITICAL", "b"), ("INFO", "b"))
    report = Report(result=result)

    rows = read_csv(report.to_csv())

    levels = {key: int(value) for section, key, value in rows if section == "level"}
    sources = {key: int(value) for section, key, value in rows if section == "source"}
    assert levels == report.to_dict()["by_level"]
    assert sources == report.to_dict()["by_source"]


def test_csv_empty_report():
    rows = read_csv(Report(result=AnalysisResult()).to_csv())

    assert ["total", "", "0"] in rows
    assert ["first_timestamp", "", ""] in rows
    assert not [row for row in rows if row[0] in ("source", "top_error_source")]


def test_csv_report_keeps_cyrillic_and_commas():
    report = Report(result=make_result(("ERROR", "сервис, один")))

    rows = read_csv(report.to_csv())

    assert ["source", "сервис, один", "1"] in rows


def test_render_unsupported_format():
    with pytest.raises(expected_exception=UnsupportedFormatError):
        Report(result=AnalysisResult()).render(fmt="xml")


def test_write_csv_file(tmp_path):
    path = tmp_path / "report.csv"

    Report(result=make_result(("ERROR", "сервис"))).write(path=path, fmt="csv")

    rows = read_csv(path.read_text(encoding="utf-8"))
    assert ["top_error_source", "сервис", "1"] in rows
