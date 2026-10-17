import json
from pathlib import Path

CSV_HEADER = "timestamp,level,source,message"


def jsonl_line(
    timestamp: object = "2024-01-01T10:00:00",
    level: object = "INFO",
    source: object = "auth",
    message: object = "ok",
) -> str:
    return json.dumps(
        obj={
            "timestamp": timestamp,
            "level": level,
            "source": source,
            "message": message,
        },
        ensure_ascii=False,
    )


def csv_line(
    timestamp: str = "2024-01-01T10:00:00",
    level: str = "INFO",
    source: str = "auth",
    message: str = "ok",
) -> str:
    return f"{timestamp},{level},{source},{message}"


def write_lines(path: Path, lines: list[str]) -> Path:
    path.write_text(data="\n".join(lines) + "\n", encoding="utf-8")
    return path
