import json
import subprocess
import sys

from tests.helpers import jsonl_line, write_lines


def run_cli(args, cwd):
    return subprocess.run(
        args=[sys.executable, "-m", "streamstats", *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=cwd,
        check=False,
    )


def good_file(tmp_path, name="data.jsonl"):
    lines = [jsonl_line(level="ERROR", source="сервис"), jsonl_line(source="auth")]
    return write_lines(path=tmp_path / name, lines=lines)


def broken_file(tmp_path):
    lines = [jsonl_line(source="a"), "{broken", jsonl_line(source="b")]
    return write_lines(path=tmp_path / "bad.jsonl", lines=lines)


def test_help(tmp_path):
    result = run_cli(args=["--help"], cwd=tmp_path)

    assert result.returncode == 0
    assert "analyze" in result.stdout


def test_report_is_written_to_file(tmp_path):
    source = good_file(tmp_path=tmp_path)
    output = tmp_path / "report.json"

    result = run_cli(
        args=["analyze", source, "--format", "jsonl", "--output", output],
        cwd=tmp_path,
    )

    assert result.returncode == 0
    text = output.read_text(encoding="utf-8")
    assert "сервис" in text
    assert json.loads(s=text)["total"] == 2


def test_report_goes_to_stdout_without_output(tmp_path):
    source = good_file(tmp_path=tmp_path)

    result = run_cli(args=["analyze", source, "--format", "jsonl"], cwd=tmp_path)

    assert result.returncode == 0
    assert json.loads(s=result.stdout)["total"] == 2


def test_multiple_inputs(tmp_path):
    first = good_file(tmp_path=tmp_path, name="1.jsonl")
    second = good_file(tmp_path=tmp_path, name="2.jsonl")

    result = run_cli(args=["analyze", first, second, "--format", "jsonl"], cwd=tmp_path)

    assert json.loads(s=result.stdout)["total"] == 4


def test_invalid_line_exits_with_2(tmp_path):
    source = broken_file(tmp_path=tmp_path)
    output = tmp_path / "report.json"

    result = run_cli(
        args=["analyze", source, "--format", "jsonl", "--output", output],
        cwd=tmp_path,
    )

    assert result.returncode == 2
    assert "bad.jsonl:2" in result.stderr
    assert not output.exists()


def test_skip_invalid(tmp_path):
    source = broken_file(tmp_path=tmp_path)

    result = run_cli(
        args=["analyze", source, "--format", "jsonl", "--skip-invalid"],
        cwd=tmp_path,
    )

    report = json.loads(s=result.stdout)
    assert result.returncode == 0
    assert report["total"] == 2
    assert report["skipped"] == 1
    assert "WARNING" in result.stderr


def test_missing_input_exits_with_2(tmp_path):
    result = run_cli(args=["analyze", "nope.jsonl", "--format", "jsonl"], cwd=tmp_path)

    assert result.returncode == 2


def test_input_file_is_not_modified(tmp_path):
    source = broken_file(tmp_path=tmp_path)
    before = source.read_bytes()

    run_cli(
        args=["analyze", source, "--format", "jsonl", "--skip-invalid"],
        cwd=tmp_path,
    )

    assert source.read_bytes() == before


def test_csv_report_to_file(tmp_path):
    source = good_file(tmp_path=tmp_path)
    output = tmp_path / "report.csv"

    result = run_cli(
        args=[
            "analyze",
            source,
            "--format",
            "jsonl",
            "--report-format",
            "csv",
            "--output",
            output,
        ],
        cwd=tmp_path,
    )

    assert result.returncode == 0
    lines = output.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "section,key,value"
    assert "total,,2" in lines
    assert "top_error_source,сервис,1" in lines


def test_csv_report_to_stdout(tmp_path):
    source = good_file(tmp_path=tmp_path)

    result = run_cli(
        args=["analyze", source, "--format", "jsonl", "--report-format", "csv"],
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert result.stdout.splitlines()[0] == "section,key,value"
    assert not result.stdout.endswith("\n\n")


def test_unknown_report_format_exits_with_2(tmp_path):
    source = good_file(tmp_path=tmp_path)

    result = run_cli(
        args=["analyze", source, "--format", "jsonl", "--report-format", "xml"],
        cwd=tmp_path,
    )

    assert result.returncode == 2


def timed_file(tmp_path):
    lines = [
        jsonl_line(timestamp="2024-01-01T09:00:00", level="INFO", source="a"),
        jsonl_line(timestamp="2024-01-01T10:00:00", level="ERROR", source="a"),
        jsonl_line(timestamp="2024-01-01T11:00:00", level="CRITICAL", source="b"),
        jsonl_line(timestamp="2024-01-01T12:00:00", level="DEBUG", source="b"),
    ]
    return write_lines(path=tmp_path / "timed.jsonl", lines=lines)


def analyze_timed(tmp_path, *filter_args):
    source = timed_file(tmp_path=tmp_path)
    return run_cli(
        args=["analyze", source, "--format", "jsonl", *filter_args],
        cwd=tmp_path,
    )


def test_level_filter(tmp_path):
    result = analyze_timed(tmp_path, "--level", "ERROR", "--level", "CRITICAL")

    report = json.loads(s=result.stdout)
    assert result.returncode == 0
    assert report["total"] == 2
    assert report["by_level"]["INFO"] == 0


def test_source_filter(tmp_path):
    result = analyze_timed(tmp_path, "--source", "b")

    report = json.loads(s=result.stdout)
    assert result.returncode == 0
    assert report["by_source"] == {"b": 2}


def test_time_filter(tmp_path):
    result = analyze_timed(
        tmp_path, "--since", "2024-01-01T10:00:00", "--until", "2024-01-01T12:00:00"
    )

    report = json.loads(s=result.stdout)
    assert result.returncode == 0
    assert report["total"] == 2
    assert report["first_timestamp"] == "2024-01-01T10:00:00+00:00"
    assert report["last_timestamp"] == "2024-01-01T11:00:00+00:00"


def test_since_with_time_zone(tmp_path):
    result = analyze_timed(tmp_path, "--since", "2024-01-01T14:00:00+03:00")

    assert json.loads(s=result.stdout)["total"] == 2


def test_filters_are_combined(tmp_path):
    result = analyze_timed(
        tmp_path, "--level", "ERROR", "--level", "CRITICAL", "--source", "b"
    )

    assert json.loads(s=result.stdout)["total"] == 1


def test_invalid_since_exits_with_2(tmp_path):
    result = analyze_timed(tmp_path, "--since", "not-a-date")

    assert result.returncode == 2
    assert "--since" in result.stderr


def test_unknown_level_exits_with_2(tmp_path):
    result = analyze_timed(tmp_path, "--level", "NOTICE")

    assert result.returncode == 2
    assert "--level" in result.stderr


def test_since_after_until_exits_with_2(tmp_path):
    result = analyze_timed(
        tmp_path, "--since", "2024-01-02T00:00:00", "--until", "2024-01-01T00:00:00"
    )

    assert result.returncode == 2
    assert "since" in result.stderr


def test_filter_does_not_hide_invalid_line(tmp_path):
    source = broken_file(tmp_path=tmp_path)

    result = run_cli(
        args=["analyze", source, "--format", "jsonl", "--source", "nobody"],
        cwd=tmp_path,
    )

    assert result.returncode == 2
    assert "bad.jsonl:2" in result.stderr
