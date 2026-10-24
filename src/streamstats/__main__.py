import argparse
import importlib
import logging
import sys
from pathlib import Path

from streamstats.analysis import Analyzer
from streamstats.constants import EXIT_ERROR, EXIT_OK
from streamstats.core import EventsLevels, to_utc
from streamstats.errors import CLIConfigurationError, StreamStatsError
from streamstats.filters import EventsFilters
from streamstats.parsers import PARSERS
from streamstats.report import REPORT_FORMATS, Report


def load_plugins(argv: list[str] | None = None) -> None:
    """
    Import modules from --plugin, they register their parsers on import.
    It runs before the main parser is built, because choices of --format
    depend on registered parsers
    :param argv: CLI arguments, sys.argv if None
    :return: None
    """
    pre_parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    pre_parser.add_argument("--plugin", action="append", default=[])
    known, _ = pre_parser.parse_known_args(argv)
    for module in known.plugin:
        try:
            importlib.import_module(module)
        except ImportError as e:
            raise CLIConfigurationError(
                reason=f"cannot import plugin {module}: {e}"
            ) from e


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
        "--report-format",
        choices=REPORT_FORMATS,
        default="json",
        help="report format (default: json)",
    )
    analyze.add_argument(
        "--skip-invalid",
        action="store_true",
        help="skip invalid lines with a warning instead of stopping",
    )

    analyze.add_argument(
        "--plugin",
        action="append",
        metavar="MODULE",
        help="module that registers extra parsers, can be repeated",
    )

    # filters
    analyze.add_argument(
        "--level", action="append", choices=[level.value for level in EventsLevels]
    )
    analyze.add_argument("--source", action="append")
    analyze.add_argument("--since", type=to_utc)
    analyze.add_argument("--until", type=to_utc)

    return parser.parse_args()


def main() -> int:
    """
    Entry point
    :return: exit code, EXIT_ERROR if processing stopped by an error
    """
    logging.basicConfig(format="%(levelname)s: %(message)s")

    try:
        load_plugins()
        args = parse_args()
        if (
            args.since is not None
            and args.until is not None
            and args.since >= args.until
        ):
            raise CLIConfigurationError(reason="since must be earlier than until")
        levels = (
            frozenset(EventsLevels(v) for v in args.level)
            if args.level is not None
            else None
        )
        sources = frozenset(args.source) if args.source is not None else None
        filters = EventsFilters(
            levels=levels, sources=sources, since=args.since, until=args.until
        )
        result = Analyzer(
            fmt=args.format, skip_invalid=args.skip_invalid, event_filter=filters
        ).analyze(args.inputs)
        report = Report(result=result)
        if args.output is None:
            print(report.render(fmt=args.report_format).rstrip("\n"))
        else:
            report.write(path=args.output, fmt=args.report_format)
    except StreamStatsError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_ERROR
    except OSError as e:
        print(f"error: cannot write report: {e}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
