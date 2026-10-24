"""
Peak memory of streamstats on big generated files.
Works on macOS and Linux. Example:
    uv run python scripts/measure_memory.py --sizes 10 100 600
"""

import argparse
import os
import platform
import random
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

BYTES_IN_MB = 1024 * 1024
BATCH_LINES = 20_000
LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
START = datetime(2024, 1, 1, tzinfo=UTC)


def generate(path: Path, size_mb: int, sources: int, seed: int) -> int:
    """
    Write JSONL file of at least size_mb, batch by batch
    :param path: file to write
    :param size_mb: target size in MB
    :param sources: number of different sources
    :param seed: random seed, the same seed gives the same file
    :return: number of lines
    """
    rng = random.Random(seed)
    target = size_mb * BYTES_IN_MB
    written = 0
    lines = 0
    with open(path, "wb") as f:
        while written < target:
            batch = []
            for _ in range(BATCH_LINES):
                timestamp = (START + timedelta(seconds=lines)).isoformat()
                batch.append(
                    f'{{"timestamp": "{timestamp}", "level": "{rng.choice(LEVELS)}", '
                    f'"source": "service-{rng.randrange(sources)}", '
                    f'"message": "сообщение {lines}"}}\n'
                )
                lines += 1
            data = "".join(batch).encode("utf-8")
            f.write(data)
            written += len(data)
    return lines


def run_cli(path: Path, report: Path) -> tuple[float, float]:
    """
    Run streamstats on the file and measure the child process only
    :param path: input file
    :param report: where the CLI writes the report
    :return: time in seconds, peak memory in MB
    """
    command = [
        sys.executable,
        "-m",
        "streamstats",
        "analyze",
        str(path),
        "--format",
        "jsonl",
        "--output",
        str(report),
    ]
    started = time.perf_counter()
    process = subprocess.Popen(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    _, status, usage = os.wait4(process.pid, 0)
    seconds = time.perf_counter() - started
    process.returncode = os.waitstatus_to_exitcode(status)
    if process.returncode != 0:
        raise RuntimeError(f"streamstats exited with code {process.returncode}")
    # ru_maxrss is in bytes on macOS and in kilobytes on Linux
    divisor = BYTES_IN_MB if sys.platform == "darwin" else 1024
    return seconds, usage.ru_maxrss / divisor


def main() -> None:
    """
    Generate a file of every size, run streamstats on it and print a table
    :return: None
    """
    parser = argparse.ArgumentParser(description="Measure peak memory of streamstats")
    parser.add_argument("--sizes", type=int, nargs="+", default=[10, 100, 600])
    parser.add_argument("--sources", type=int, default=100)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    print(f"Python {platform.python_version()}, {platform.platform()}")
    print(f"sources: {args.sources}, seed: {args.seed}\n")
    print("| File, MB | Lines | Time, s | Peak memory, MB |")
    print("|---|---|---|---|")
    for size_mb in args.sizes:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            lines = generate(path, size_mb, args.sources, args.seed)
            seconds, peak = run_cli(path, Path(tmp) / "report.json")
            real_mb = path.stat().st_size / BYTES_IN_MB
        print(f"| {real_mb:.0f} | {lines:,} | {seconds:.1f} | {peak:.1f} |", flush=True)


if __name__ == "__main__":
    main()
