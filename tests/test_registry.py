import pytest

from streamstats.analysis import Analyzer
from streamstats.errors import (
    CLIConfigurationError,
    InvalidEventError,
    StreamStatsError,
    error_position,
)
from streamstats.parsers import PARSERS, BaseParser, register_parser
from tests.helpers import write_lines


@pytest.fixture(autouse=True)
def restore_parsers():
    before = dict(PARSERS)
    yield
    PARSERS.clear()
    PARSERS.update(before)


def register_plain_parser():
    """Custom format, one event per line: LEVEL source message"""

    @register_parser(name="plain")
    class PlainParser(BaseParser):
        def parse(self, lines, source_name):
            for line_no, raw in enumerate(lines, start=1):
                try:
                    with error_position(path=source_name, line=line_no):
                        parts = raw.split(maxsplit=2)
                        if len(parts) != 3:
                            raise InvalidEventError(message="expected 3 parts")
                        level, source, message = parts
                        event = self._build_event(
                            record={
                                "timestamp": "2024-01-01T10:00:00",
                                "level": level,
                                "source": source,
                                "message": message,
                            }
                        )
                except StreamStatsError as e:
                    self._handle_error(source_name=source_name, line=line_no, error=e)
                    continue
                yield event

    return PlainParser


def test_builtin_formats_are_registered():
    assert {"csv", "jsonl"} <= set(PARSERS)


def test_decorator_returns_class_and_registers_it():
    parser_class = register_plain_parser()

    assert PARSERS["plain"] is parser_class


def test_registered_format_works_in_analyzer(tmp_path):
    register_plain_parser()
    path = write_lines(
        path=tmp_path / "events.log",
        lines=["ERROR db disk is full", "INFO web all good"],
    )

    result = Analyzer(fmt="plain").analyze(paths=[path])

    assert result.total == 2
    assert dict(result.errors_by_source) == {"db": 1}


def test_registered_format_supports_skip_mode(tmp_path):
    register_plain_parser()
    path = write_lines(
        path=tmp_path / "events.log", lines=["ERROR db x", "broken", "INFO web y"]
    )

    result = Analyzer(fmt="plain", skip_invalid=True).analyze(paths=[path])

    assert result.total == 2
    assert result.skipped == 1


def test_registered_format_strict_mode_reports_line(tmp_path):
    register_plain_parser()
    path = write_lines(path=tmp_path / "events.log", lines=["ERROR db x", "broken"])

    with pytest.raises(
        expected_exception=InvalidEventError, match=r"events\.log:2: expected 3"
    ):
        Analyzer(fmt="plain").analyze(paths=[path])


def test_duplicate_name_is_rejected():
    register_plain_parser()

    with pytest.raises(expected_exception=CLIConfigurationError, match="plain"):
        register_plain_parser()


def test_builtin_name_cannot_be_replaced():
    with pytest.raises(expected_exception=CLIConfigurationError, match="csv"):
        register_parser(name="csv")(BaseParser)


def test_only_parser_classes_can_be_registered():
    with pytest.raises(expected_exception=TypeError):
        register_parser(name="not_a_parser")(dict)
