import re
from datetime import date, datetime, timedelta
from pathlib import PurePosixPath
from typing import Annotated

import pandas as pd

SavePathType = Annotated[str, "File path to save data. If None, data is not saved."]

# Tickers can contain letters, digits, dot, dash, underscore, caret
# (index symbols like ^GSPC), equals (futures like GC=F), and plus
# (forex/CFD symbols like XAUUSD+). None of these enable directory
# traversal, so the value never escapes a containing directory when
# interpolated into a path. Anything else is rejected.
_TICKER_PATH_RE = re.compile(r"^[A-Za-z0-9._\-\^=+]+$")


def safe_ticker_component(value: str, *, max_len: int = 32) -> str:
    """Validate ``value`` is safe to interpolate into a filesystem path.

    Tickers come from user CLI input or from LLM tool calls, both of which
    can be influenced by attacker-controlled content (e.g. prompt injection
    embedded in fetched news). Without validation, a value like
    ``"../../../etc/foo"`` flows into ``os.path.join`` / ``Path /`` and
    escapes the configured cache, checkpoint, or results directory.

    Returns ``value`` unchanged when it matches the allowed pattern; raises
    ``ValueError`` otherwise.
    """
    if not isinstance(value, str) or not value:
        raise ValueError(f"ticker must be a non-empty string, got {value!r}")
    if len(value) > max_len:
        raise ValueError(f"ticker exceeds {max_len} chars: {value!r}")
    if not _TICKER_PATH_RE.fullmatch(value):
        raise ValueError(
            f"ticker contains characters not allowed in a filesystem path: {value!r}"
        )
    # The regex above allows '.', so values like '.', '..', '...' would pass,
    # and as a path component they traverse the parent directory. Reject any
    # value that's only dots.
    if set(value) == {"."}:
        raise ValueError(f"ticker cannot consist solely of dots: {value!r}")
    return value


def render_report_path(template: str, *, ticker: str, analysis_date: str) -> PurePosixPath:
    """Render the per-run report subdirectory from a user-supplied template.

    The result is a *relative* PurePosixPath that callers join to
    ``config["results_dir"]``. Returning a relative path (not an absolute one)
    is part of the contract — it prevents a malicious or buggy template from
    escaping the configured results root.

    Supported template variables:
        {ticker}         — the ticker symbol, sanitized via safe_ticker_component
        {analysis_date}  — the YYYY-MM-DD analysis date string
        {year}, {month}, {day} — components of analysis_date as zero-padded strings

    Example:
        >>> render_report_path("{ticker}/{analysis_date}/reports",
        ...                    ticker="AAPL", analysis_date="2026-05-22")
        PurePosixPath('AAPL/2026-05-22/reports')
    """
    safe = safe_ticker_component(ticker)
    parsed = datetime.strptime(analysis_date, "%Y-%m-%d")
    variables = {
        "ticker": safe,
        "analysis_date": analysis_date,
        "year": f"{parsed.year:04d}",
        "month": f"{parsed.month:02d}",
        "day": f"{parsed.day:02d}",
    }
    rendered = template.format_map(variables)
    path = PurePosixPath(rendered)
    if not path.parts or path.is_absolute() or any(p == ".." for p in path.parts):
        raise ValueError(
            "report_path_template must render to a relative, non-empty path "
            f"with no '..' segments: template={template!r} rendered={rendered!r}"
        )
    return path


def save_output(data: pd.DataFrame, tag: str, save_path: SavePathType = None) -> None:
    if save_path:
        data.to_csv(save_path, encoding="utf-8")
        print(f"{tag} saved to {save_path}")


def get_current_date():
    return date.today().strftime("%Y-%m-%d")


def decorate_all_methods(decorator):
    def class_decorator(cls):
        for attr_name, attr_value in cls.__dict__.items():
            if callable(attr_value):
                setattr(cls, attr_name, decorator(attr_value))
        return cls

    return class_decorator


def get_next_weekday(date):

    if not isinstance(date, datetime):
        date = datetime.strptime(date, "%Y-%m-%d")

    if date.weekday() >= 5:
        days_to_add = 7 - date.weekday()
        next_weekday = date + timedelta(days=days_to_add)
        return next_weekday
    else:
        return date
