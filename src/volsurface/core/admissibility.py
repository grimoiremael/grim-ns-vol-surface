"""Quote admissibility checks for normalized option quotes."""

from __future__ import annotations

import math
from datetime import datetime
from numbers import Real
from typing import Any

from volsurface.core.schema import (
    AdmissibilityFlag,
    AdmissibilityReport,
    AdmissibilitySeverity,
    NormalizedOptionQuote,
)


ZERO_MARKET = "ZERO_MARKET"
INVERTED_MARKET = "INVERTED_MARKET"
WIDE_SPREAD = "WIDE_SPREAD"
LOW_MID = "LOW_MID"
INVALID_STRIKE = "INVALID_STRIKE"
INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
LOW_LIQUIDITY = "LOW_LIQUIDITY"

DEFAULT_MAX_RELATIVE_SPREAD = 0.50
DEFAULT_MIN_MIDPOINT = 0.01
DEFAULT_MIN_VOLUME = 1
DEFAULT_MIN_OPEN_INTEREST = 1


def evaluate_quote_admissibility(
    quote: NormalizedOptionQuote,
    *,
    max_relative_spread: float = DEFAULT_MAX_RELATIVE_SPREAD,
    min_midpoint: float = DEFAULT_MIN_MIDPOINT,
    min_volume: int | None = DEFAULT_MIN_VOLUME,
    min_open_interest: int | None = DEFAULT_MIN_OPEN_INTEREST,
    require_quote_timestamp: bool = False,
) -> AdmissibilityReport:
    """Evaluate normalized quote quality without computing implied volatility."""

    if not isinstance(quote, NormalizedOptionQuote):
        raise TypeError("quote must be a NormalizedOptionQuote")

    _validate_thresholds(
        max_relative_spread=max_relative_spread,
        min_midpoint=min_midpoint,
        min_volume=min_volume,
        min_open_interest=min_open_interest,
        require_quote_timestamp=require_quote_timestamp,
    )

    flags: list[AdmissibilityFlag] = []
    _check_strike(quote, flags)
    _check_timestamps(quote, flags, require_quote_timestamp=require_quote_timestamp)
    _check_market_shape(
        quote,
        flags,
        max_relative_spread=float(max_relative_spread),
        min_midpoint=float(min_midpoint),
    )
    _check_liquidity(
        quote,
        flags,
        min_volume=min_volume,
        min_open_interest=min_open_interest,
    )

    return AdmissibilityReport(
        flags=tuple(flags),
        quote_id=_safe_quote_id(getattr(quote, "quote_id", None)),
    )


def _check_strike(
    quote: NormalizedOptionQuote,
    flags: list[AdmissibilityFlag],
) -> None:
    strike = _finite_float(getattr(quote, "strike", None))
    if strike is None or strike <= 0.0:
        flags.append(
            _flag(
                INVALID_STRIKE,
                "Strike must be a finite positive number.",
                AdmissibilitySeverity.REJECT,
            )
        )


def _check_timestamps(
    quote: NormalizedOptionQuote,
    flags: list[AdmissibilityFlag],
    *,
    require_quote_timestamp: bool,
) -> None:
    expiry = getattr(quote, "expiry", None)
    quote_timestamp = getattr(quote, "quote_timestamp", None)

    if not isinstance(expiry, datetime):
        flags.append(
            _flag(
                INVALID_TIMESTAMP,
                "Expiry timestamp is missing or invalid.",
                AdmissibilitySeverity.REJECT,
            )
        )
        return

    if quote_timestamp is None:
        if require_quote_timestamp:
            flags.append(
                _flag(
                    INVALID_TIMESTAMP,
                    "Quote timestamp is required for this admissibility check.",
                    AdmissibilitySeverity.REJECT,
                )
            )
        return

    if not isinstance(quote_timestamp, datetime):
        flags.append(
            _flag(
                INVALID_TIMESTAMP,
                "Quote timestamp is invalid.",
                AdmissibilitySeverity.REJECT,
            )
        )
        return

    try:
        if expiry <= quote_timestamp:
            flags.append(
                _flag(
                    INVALID_TIMESTAMP,
                    "Expiry must be after quote timestamp.",
                    AdmissibilitySeverity.REJECT,
                )
            )
    except TypeError:
        flags.append(
            _flag(
                INVALID_TIMESTAMP,
                "Expiry and quote timestamp must use compatible timezone awareness.",
                AdmissibilitySeverity.REJECT,
            )
        )


def _check_market_shape(
    quote: NormalizedOptionQuote,
    flags: list[AdmissibilityFlag],
    *,
    max_relative_spread: float,
    min_midpoint: float,
) -> None:
    bid = _finite_float(getattr(quote, "bid", None))
    ask = _finite_float(getattr(quote, "ask", None))
    if bid is None or ask is None or bid < 0.0 or ask < 0.0:
        flags.append(
            _flag(
                INVERTED_MARKET,
                "Bid and ask must be finite non-negative numbers.",
                AdmissibilitySeverity.REJECT,
            )
        )
        return

    if bid == 0.0 and ask == 0.0:
        flags.append(
            _flag(
                ZERO_MARKET,
                "Bid and ask are both zero.",
                AdmissibilitySeverity.REJECT,
            )
        )

    if ask < bid:
        flags.append(
            _flag(
                INVERTED_MARKET,
                "Ask is lower than bid.",
                AdmissibilitySeverity.REJECT,
            )
        )

    midpoint = _effective_midpoint(quote, bid=bid, ask=ask)
    if midpoint < min_midpoint:
        flags.append(
            _flag(
                LOW_MID,
                f"Midpoint {midpoint:.8g} is below minimum threshold {min_midpoint:.8g}.",
                AdmissibilitySeverity.REJECT,
            )
        )

    if midpoint > 0.0 and ask >= bid:
        spread = ask - bid
        relative_spread = spread / midpoint
        if relative_spread > max_relative_spread:
            flags.append(
                _flag(
                    WIDE_SPREAD,
                    (
                        f"Relative spread {relative_spread:.4g} exceeds "
                        f"maximum {max_relative_spread:.4g}."
                    ),
                    AdmissibilitySeverity.WARNING,
                )
            )


def _check_liquidity(
    quote: NormalizedOptionQuote,
    flags: list[AdmissibilityFlag],
    *,
    min_volume: int | None,
    min_open_interest: int | None,
) -> None:
    low_fields: list[str] = []
    volume = getattr(quote, "volume", None)
    open_interest = getattr(quote, "open_interest", None)

    if min_volume is not None and volume is not None:
        volume_value = _finite_int("volume", volume)
        if volume_value is None or volume_value < min_volume:
            low_fields.append(f"volume={volume!r}")

    if min_open_interest is not None and open_interest is not None:
        open_interest_value = _finite_int("open_interest", open_interest)
        if open_interest_value is None or open_interest_value < min_open_interest:
            low_fields.append(f"open_interest={open_interest!r}")

    if low_fields:
        flags.append(
            _flag(
                LOW_LIQUIDITY,
                "Low liquidity based on " + ", ".join(low_fields) + ".",
                AdmissibilitySeverity.WARNING,
            )
        )


def _effective_midpoint(
    quote: NormalizedOptionQuote,
    *,
    bid: float,
    ask: float,
) -> float:
    quote_mid = _finite_float(getattr(quote, "mid", None))
    if quote_mid is not None and quote_mid >= 0.0:
        return quote_mid
    return (bid + ask) / 2.0


def _validate_thresholds(
    *,
    max_relative_spread: float,
    min_midpoint: float,
    min_volume: int | None,
    min_open_interest: int | None,
    require_quote_timestamp: bool,
) -> None:
    max_relative_spread_value = _finite_float(max_relative_spread)
    if max_relative_spread_value is None or max_relative_spread_value < 0.0:
        raise ValueError("max_relative_spread must be non-negative")
    min_midpoint_value = _finite_float(min_midpoint)
    if min_midpoint_value is None or min_midpoint_value < 0.0:
        raise ValueError("min_midpoint must be non-negative")
    _validate_optional_non_negative_int("min_volume", min_volume)
    _validate_optional_non_negative_int("min_open_interest", min_open_interest)
    if not isinstance(require_quote_timestamp, bool):
        raise TypeError("require_quote_timestamp must be a bool")


def _validate_optional_non_negative_int(field_name: str, value: int | None) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer or None")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")


def _finite_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool) or not isinstance(value, Real):
        return None
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        return None
    return numeric_value


def _finite_int(field_name: str, value: Any) -> int | None:
    del field_name
    if value is None or isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _safe_quote_id(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _flag(
    code: str,
    message: str,
    severity: AdmissibilitySeverity,
) -> AdmissibilityFlag:
    return AdmissibilityFlag(code=code, message=message, severity=severity)


__all__ = [
    "DEFAULT_MAX_RELATIVE_SPREAD",
    "DEFAULT_MIN_MIDPOINT",
    "DEFAULT_MIN_OPEN_INTEREST",
    "DEFAULT_MIN_VOLUME",
    "INVERTED_MARKET",
    "INVALID_STRIKE",
    "INVALID_TIMESTAMP",
    "LOW_LIQUIDITY",
    "LOW_MID",
    "WIDE_SPREAD",
    "ZERO_MARKET",
    "evaluate_quote_admissibility",
]
