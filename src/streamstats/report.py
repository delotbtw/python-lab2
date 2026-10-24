import csv
import io
import json
from collections import Counter
from pathlib import Path
from typing import Any

from streamstats.analysis import AnalysisResult
from streamstats.constants import TOP_N
from streamstats.core import EventsLevels
from streamstats.errors import UnsupportedFormatError

REPORT_FORMATS = ("json", "csv")


def get_top_n(errors_by_source: Counter[str], n: int) -> list[dict[str, Any]]:
    """
    Top of sources by errors, sources with equal count are sorted by name
    :param errors_by_source: errors count per source
    :param n: size of the top
    :return: list of sources with their counts
    """
    items = sorted(errors_by_source.items(), key=lambda x: (-x[1], x[0]))
    result = []
    for source, amount in items[:n]:
        result.append({"source": source, "count": amount})

    return result


class Report:
    """JSON report built from statistics"""

    def __init__(self, result: AnalysisResult, top_n: int = TOP_N) -> None:
        """
        :param result: statistics of all files
        :param top_n: size of the top of error sources
        :return: None
        """
        self.result = result
        self.top_n = top_n

    def to_dict(self) -> dict[str, Any]:
        """
        Build report as a dict, all levels are present even with zero count
        :return: report
        """
        dict_result: dict[str, Any] = {}
        dict_result["total"] = self.result.total
        dict_result["skipped"] = self.result.skipped

        dict_result["by_level"] = {
            level.value: self.result.total_by_level[level] for level in EventsLevels
        }
        dict_result["by_source"] = dict(sorted(self.result.total_by_source.items()))
        dict_result["top_error_sources"] = get_top_n(
            errors_by_source=self.result.errors_by_source, n=self.top_n
        )

        first = self.result.first_timestamp
        last = self.result.last_timestamp
        dict_result["first_timestamp"] = first.isoformat() if first else None
        dict_result["last_timestamp"] = last.isoformat() if last else None
        return dict_result

    def to_json(self) -> str:
        """
        Report as JSON, non-ASCII characters are kept as is
        :return: JSON string
        """
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_csv(self) -> str:
        """
        Report as CSV table with columns section, key, value.
        It is built from to_dict, so nothing is calculated twice
        :return: CSV string
        """
        data = self.to_dict()
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(["section", "key", "value"])
        writer.writerow(["total", "", data["total"]])
        writer.writerow(["skipped", "", data["skipped"]])
        for level, amount in data["by_level"].items():
            writer.writerow(["level", level, amount])
        for source, amount in data["by_source"].items():
            writer.writerow(["source", source, amount])
        for item in data["top_error_sources"]:
            writer.writerow(["top_error_source", item["source"], item["count"]])
        writer.writerow(["first_timestamp", "", data["first_timestamp"]])
        writer.writerow(["last_timestamp", "", data["last_timestamp"]])
        return buffer.getvalue()

    def render(self, fmt: str) -> str:
        """
        Report in the given format
        :param fmt: report format, json or csv
        :return: report text
        """
        if fmt not in REPORT_FORMATS:
            raise UnsupportedFormatError(fmt=fmt)
        if fmt == "csv":
            return self.to_csv()
        return self.to_json()

    def write(self, path: Path, fmt: str = "json") -> None:
        """
        Write report to file
        :param path: report file
        :param fmt: report format, json or csv
        :return: None
        """
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(self.render(fmt=fmt))
