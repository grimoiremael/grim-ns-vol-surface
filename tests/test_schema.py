from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from volsurface.core.schema import (  # noqa: E402
    AdmissibilityFlag,
    AdmissibilityReport,
    AdmissibilitySeverity,
    IVPoint,
    IVSolveResult,
    NormalizedOptionQuote,
    OptionQuote,
    OptionType,
)


QUOTE_TIME = datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc)
EXPIRY = QUOTE_TIME + timedelta(days=45)


def test_option_quote_accepts_valid_raw_quote() -> None:
    quote = OptionQuote(
        underlying="SPY",
        expiry=EXPIRY,
        option_type=OptionType.CALL,
        strike=500.0,
        bid=12.35,
        ask=12.6,
        quote_timestamp=QUOTE_TIME,
        volume=100,
        open_interest=250,
    )

    assert quote.option_type is OptionType.CALL
    assert quote.strike == 500.0


def test_option_quote_validates_basic_quote_invariants() -> None:
    with pytest.raises(ValueError, match="strike must be positive"):
        OptionQuote(
            underlying="SPY",
            expiry=EXPIRY,
            option_type=OptionType.CALL,
            strike=0.0,
        )

    with pytest.raises(ValueError, match="bid must be non-negative"):
        OptionQuote(
            underlying="SPY",
            expiry=EXPIRY,
            option_type=OptionType.PUT,
            strike=500.0,
            bid=-0.01,
        )

    with pytest.raises(ValueError, match="expiry must be after quote_timestamp"):
        OptionQuote(
            underlying="SPY",
            expiry=QUOTE_TIME,
            option_type=OptionType.PUT,
            strike=500.0,
            bid=1.0,
            ask=1.2,
            quote_timestamp=QUOTE_TIME,
        )


def test_normalized_option_quote_validates_required_bid_ask_and_context() -> None:
    quote = NormalizedOptionQuote(
        underlying="SPY",
        expiry=EXPIRY,
        option_type="put",
        strike=475.0,
        bid=6.1,
        ask=6.4,
        mid=6.25,
        spot=490.0,
        forward=491.0,
        risk_free_rate=0.04,
        dividend_yield=0.01,
        quote_timestamp=QUOTE_TIME,
    )

    assert quote.option_type is OptionType.PUT

    with pytest.raises(ValueError, match="ask must be non-negative"):
        NormalizedOptionQuote(
            underlying="SPY",
            expiry=EXPIRY,
            option_type=OptionType.PUT,
            strike=475.0,
            bid=6.1,
            ask=-0.01,
        )

    with pytest.raises(ValueError, match="spot must be positive"):
        NormalizedOptionQuote(
            underlying="SPY",
            expiry=EXPIRY,
            option_type=OptionType.PUT,
            strike=475.0,
            bid=6.1,
            ask=6.4,
            spot=0.0,
        )


def test_admissibility_report_exposes_accepted_warning_and_rejected_states() -> None:
    assert AdmissibilityReport().is_admissible is True

    warning_report = AdmissibilityReport(
        flags=(
            AdmissibilityFlag(
                code="wide_spread",
                message="Bid/ask spread is wider than review threshold.",
                severity=AdmissibilitySeverity.WARNING,
            ),
        )
    )

    assert warning_report.is_admissible is True
    assert warning_report.has_warnings is True
    assert warning_report.warning_messages == (
        "Bid/ask spread is wider than review threshold.",
    )

    rejected_report = AdmissibilityReport(
        flags=(
            AdmissibilityFlag(
                code="stale_quote",
                message="Quote timestamp is stale.",
                severity="reject",
            ),
        )
    )

    assert rejected_report.is_admissible is False
    assert rejected_report.rejection_reasons == ("Quote timestamp is stale.",)


def test_iv_solve_result_validates_success_and_failure_shapes() -> None:
    success = IVSolveResult(
        converged=True,
        implied_volatility=0.24,
        iterations=7,
        objective_value=0.0,
        lower_bound=0.0001,
        upper_bound=5.0,
    )

    assert success.implied_volatility == 0.24

    with pytest.raises(ValueError, match="implied_volatility is required"):
        IVSolveResult(converged=True)

    failure = IVSolveResult(
        converged=False,
        iterations=20,
        failure_reason="No bracket found.",
    )

    assert failure.failure_reason == "No bracket found."

    with pytest.raises(ValueError, match="failure_reason is required"):
        IVSolveResult(converged=False)


def test_iv_point_validates_solved_point_invariants() -> None:
    solve_result = IVSolveResult(converged=True, implied_volatility=0.31)
    point = IVPoint(
        underlying="SPY",
        expiry=EXPIRY,
        option_type=OptionType.CALL,
        strike=505.0,
        implied_volatility=0.31,
        quote_timestamp=QUOTE_TIME,
        time_to_expiry_years=45 / 365,
        forward=491.0,
        moneyness=505.0 / 491.0,
        solve_result=solve_result,
    )

    assert point.solve_result is solve_result

    with pytest.raises(ValueError, match="implied_volatility must be non-negative"):
        IVPoint(
            underlying="SPY",
            expiry=EXPIRY,
            option_type=OptionType.CALL,
            strike=505.0,
            implied_volatility=-0.01,
        )

    with pytest.raises(ValueError, match="solve_result must be converged"):
        IVPoint(
            underlying="SPY",
            expiry=EXPIRY,
            option_type=OptionType.CALL,
            strike=505.0,
            implied_volatility=0.31,
            solve_result=IVSolveResult(
                converged=False,
                failure_reason="No valid root.",
            ),
        )
