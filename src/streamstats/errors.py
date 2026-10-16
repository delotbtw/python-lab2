from collections.abc import Generator
from contextlib import contextmanager


class StreamStatsError(Exception):
    """Base class of errors in project"""

    path: str | None = None
    line: int | None = None

    def __str__(self) -> str:
        text = super().__str__()
        if self.path is not None:
            return f"{self.path}:{self.line}: {text}"
        return text


class InvalidEventError(StreamStatsError):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class InvalidTimestampError(StreamStatsError):
    def __init__(self, value: str) -> None:
        self.value = value
        super().__init__(f"invalid timestamp: {value}")


class CLIConfigurationError(StreamStatsError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"wrong CLI configuration: {reason}")


class UnsupportedFormatError(StreamStatsError):
    def __init__(self, fmt: str) -> None:
        self.fmt = fmt
        super().__init__(f"unsupported format: {fmt}")


@contextmanager
def error_position(path: str, line: int) -> Generator[None]:
    try:
        yield
    except StreamStatsError as e:
        e.path = path
        e.line = line
        raise
