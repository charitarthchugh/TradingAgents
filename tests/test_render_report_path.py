from pathlib import PurePosixPath

import pytest

from tradingagents.dataflows.utils import render_report_path


def test_default_template_renders_expected_layout():
    result = render_report_path(
        "{ticker}/{analysis_date}/reports",
        ticker="AAPL",
        analysis_date="2026-05-22",
    )
    assert result == PurePosixPath("AAPL/2026-05-22/reports")


def test_date_components_are_zero_padded():
    result = render_report_path(
        "{year}/{month}/{day}/{ticker}",
        ticker="AAPL",
        analysis_date="2026-01-07",
    )
    assert result == PurePosixPath("2026/01/07/AAPL")


def test_unknown_template_key_fails_loudly():
    with pytest.raises(KeyError):
        render_report_path(
            "{provider}/{ticker}",
            ticker="AAPL",
            analysis_date="2026-05-22",
        )


def test_path_traversal_in_template_is_rejected():
    with pytest.raises(ValueError, match="must render to a relative"):
        render_report_path(
            "../{ticker}/reports",
            ticker="AAPL",
            analysis_date="2026-05-22",
        )


def test_absolute_template_is_rejected():
    with pytest.raises(ValueError, match="must render to a relative"):
        render_report_path(
            "/etc/{ticker}",
            ticker="AAPL",
            analysis_date="2026-05-22",
        )


def test_empty_template_is_rejected():
    with pytest.raises(ValueError, match="must render to a relative"):
        render_report_path(
            "",
            ticker="AAPL",
            analysis_date="2026-05-22",
        )


def test_malicious_ticker_is_rejected_before_substitution():
    with pytest.raises(ValueError, match="ticker"):
        render_report_path(
            "{ticker}/reports",
            ticker="../../etc/passwd",
            analysis_date="2026-05-22",
        )


def test_malformed_date_is_rejected():
    with pytest.raises(ValueError):
        render_report_path(
            "{year}/{ticker}",
            ticker="AAPL",
            analysis_date="not-a-date",
        )
