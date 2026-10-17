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
