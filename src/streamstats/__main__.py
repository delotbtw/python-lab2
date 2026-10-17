import argparse
import logging
import sys
from pathlib import Path

from streamstats.analysis import Analyzer
from streamstats.constants import EXIT_ERROR, EXIT_OK
from streamstats.errors import StreamStatsError
from streamstats.parsers import PARSERS
from streamstats.report import Report


def parse_args() -> argparse.Namespace:
    """
    CLI argument parser
    :return: parsed arguments
    """
    parser = argparse.ArgumentParser(
        prog="streamstats",
        description="Streaming statistics for CSV and JSONL event files.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser(
        "analyze", help="analyze event files and build a JSON report"
    )
    analyze.add_argument("inputs", nargs="+", type=Path, metavar="INPUT")
    analyze.add_argument("--format", required=True, choices=sorted(PARSERS))
    analyze.add_argument("--output", type=Path, help="report file (default: stdout)")
    analyze.add_argument(
        "--skip-invalid",
        action="store_true",
        help="skip invalid lines with a warning instead of stopping",
    )
    return parser.parse_args()


def main() -> int:
    """
    Entry point
    :return: exit code, EXIT_ERROR if processing stopped by an error
    """
    logging.basicConfig(format="%(levelname)s: %(message)s")
    args = parse_args()

    try:
        result = Analyzer(args.format, args.skip_invalid).analyze(args.inputs)
        report = Report(result)
        if args.output is None:
            print(report.to_json())
        else:
            report.write(args.output)
    except StreamStatsError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_ERROR
    except OSError as e:
        print(f"error: cannot write report: {e}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
