from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from volsurface.core.admissibility import (  # noqa: E402
    INVERTED_MARKET,
    INVALID_STRIKE,
    INVALID_TIMESTAMP,
    LOW_LIQUIDITY,
    LOW_MID,
    WIDE_SPREAD,
    ZERO_MARKET,
    evaluate_quote_admissibility,
)
from volsurface.core.schema import (  # noqa: E402
    AdmissibilitySeverity,
    NormalizedOptionQuote,
    OptionType,
)


QUOTE_TIME = datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc)
EXPIRY = QUOTE_TIME + timedelta(days=30)


def _quote(**overrides: object) -> NormalizedOptionQuote:
    kwargs = {
        "underlying": "SPY",
        "expiry": EXPIRY,
        "option_type": OptionType.CALL,
        "strike": 500.0,
        "bid": 10.0,
        "ask": 10.4,
        "quote_timestamp": QUOTE_TIME,
        "mid": None,
        "volume": 100,
        "open_interest": 250,
        "quote_id": "SPY-C-500",
    }
    kwargs.update(overrides)
    return NormalizedOptionQuote(**kwargs)


def _unsafe_quote(**overrides: object) -> NormalizedOptionQuote:
    quote = _quote()
    unsafe_quote = object.__new__(NormalizedOptionQuote)
    for field in fields(NormalizedOptionQuote):
        object.__setattr__(unsafe_quote, field.name, getattr(quote, field.name))
    for name, value in overrides.items():
        object.__setattr__(unsafe_quote, name, value)
    return unsafe_quote


def _codes(report) -> set[str]:
    return {flag.code for flag in report.flags}


def _flag(report, code: str):
    return next(flag for flag in report.flags if flag.code == code)


def test_clean_quote_is_admissible_without_flags() -> None:
    report = evaluate_quote_admissibility(_quote())

    assert report.is_admissible is True
    assert report.has_warnings is False
    assert report.flags == ()
    assert report.quote_id == "SPY-C-500"


def test_zero_bid_and_zero_ask_rejects_quote() -> None:
    report = evaluate_quote_admissibility(_quote(bid=0.0, ask=0.0, mid=0.0))

    assert report.is_admissible is False
    assert ZERO_MARKET in _codes(report)
    assert LOW_MID in _codes(report)
    assert _flag(report, ZERO_MARKET).severity is AdmissibilitySeverity.REJECT


def test_inverted_market_rejects_quote() -> None:
    report = evaluate_quote_admissibility(_unsafe_quote(bid=2.0, ask=1.0))

    assert report.is_admissible is False
    assert INVERTED_MARKET in _codes(report)
    assert _flag(report, INVERTED_MARKET).severity is AdmissibilitySeverity.REJECT


def test_wide_spread_warns_without_rejecting_quote() -> None:
    report = evaluate_quote_admissibility(_quote(bid=1.0, ask=3.0))

    assert report.is_admissible is True
    assert report.has_warnings is True
    assert _codes(report) == {WIDE_SPREAD}
    assert _flag(report, WIDE_SPREAD).severity is AdmissibilitySeverity.WARNING


def test_low_midpoint_rejects_quote() -> None:
    report = evaluate_quote_admissibility(_quote(bid=0.002, ask=0.004))

    assert report.is_admissible is False
    assert LOW_MID in _codes(report)
    assert _flag(report, LOW_MID).severity is AdmissibilitySeverity.REJECT


def test_invalid_strike_rejects_quote() -> None:
    report = evaluate_quote_admissibility(_unsafe_quote(strike=0.0))

    assert report.is_admissible is False
    assert INVALID_STRIKE in _codes(report)


def test_invalid_timestamp_rejects_quote_when_expiry_is_not_after_quote_time() -> None:
    report = evaluate_quote_admissibility(_unsafe_quote(expiry=QUOTE_TIME))

    assert report.is_admissible is False
    assert INVALID_TIMESTAMP in _codes(report)


def test_missing_quote_timestamp_can_be_required() -> None:
    report = evaluate_quote_admissibility(
        _quote(quote_timestamp=None),
        require_quote_timestamp=True,
    )

    assert report.is_admissible is False
    assert INVALID_TIMESTAMP in _codes(report)


def test_low_liquidity_warns_when_present_fields_are_below_threshold() -> None:
    report = evaluate_quote_admissibility(_quote(volume=0, open_interest=0))

    assert report.is_admissible is True
    assert report.has_warnings is True
    assert _codes(report) == {LOW_LIQUIDITY}
    assert _flag(report, LOW_LIQUIDITY).severity is AdmissibilitySeverity.WARNING


def test_liquidity_check_ignores_missing_liquidity_fields() -> None:
    report = evaluate_quote_admissibility(_quote(volume=None, open_interest=None))

    assert report.is_admissible is True
    assert LOW_LIQUIDITY not in _codes(report)


def test_invalid_threshold_configuration_raises() -> None:
    with pytest.raises(ValueError, match="max_relative_spread must be non-negative"):
        evaluate_quote_admissibility(_quote(), max_relative_spread=-0.1)
