from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from volsurface.core.bsm import bsm_call_price, bsm_put_price  # noqa: E402
from volsurface.core.iv_solver import solve_implied_volatility  # noqa: E402
from volsurface.core.schema import OptionType  # noqa: E402


def test_solver_recovers_known_call_volatility_from_bsm_price() -> None:
    expected_sigma = 0.27
    market_price = bsm_call_price(
        S=100.0,
        K=102.0,
        T=0.75,
        sigma=expected_sigma,
        r=0.04,
        q=0.01,
    )

    result = solve_implied_volatility(
        option_type=OptionType.CALL,
        market_price=market_price,
        S=100.0,
        K=102.0,
        T=0.75,
        r=0.04,
        q=0.01,
    )

    assert result.converged is True
    assert result.failure_reason is None
    assert result.implied_volatility == pytest.approx(expected_sigma, abs=1e-7)


def test_solver_recovers_known_put_volatility_from_bsm_price() -> None:
    expected_sigma = 0.34
    market_price = bsm_put_price(
        S=250.0,
        K=240.0,
        T=1.25,
        sigma=expected_sigma,
        r=0.035,
        q=0.015,
    )

    result = solve_implied_volatility(
        option_type="put",
        market_price=market_price,
        S=250.0,
        K=240.0,
        T=1.25,
        r=0.035,
        q=0.015,
    )

    assert result.converged is True
    assert result.implied_volatility == pytest.approx(expected_sigma, abs=1e-7)


def test_solver_returns_zero_volatility_for_intrinsic_bsm_price() -> None:
    market_price = bsm_call_price(
        S=105.0,
        K=100.0,
        T=0.5,
        sigma=0.0,
        r=0.03,
        q=0.01,
    )

    result = solve_implied_volatility(
        option_type=OptionType.CALL,
        market_price=market_price,
        S=105.0,
        K=100.0,
        T=0.5,
        r=0.03,
        q=0.01,
    )

    assert result.converged is True
    assert result.implied_volatility == 0.0


def test_solver_reports_invalid_price_failure() -> None:
    result = solve_implied_volatility(
        option_type=OptionType.CALL,
        market_price=-0.01,
        S=100.0,
        K=100.0,
        T=1.0,
        r=0.03,
        q=0.01,
    )

    assert result.converged is False
    assert result.failure_reason is not None
    assert result.failure_reason.startswith("invalid price:")


def test_solver_reports_invalid_input_failure() -> None:
    result = solve_implied_volatility(
        option_type=OptionType.CALL,
        market_price=5.0,
        S=100.0,
        K=100.0,
        T=0.0,
        r=0.03,
        q=0.01,
    )

    assert result.converged is False
    assert result.failure_reason is not None
    assert result.failure_reason.startswith("invalid inputs:")


def test_solver_reports_no_bracket_failure() -> None:
    market_price = bsm_call_price(
        S=100.0,
        K=100.0,
        T=1.0,
        sigma=2.0,
        r=0.03,
        q=0.01,
    )

    result = solve_implied_volatility(
        option_type=OptionType.CALL,
        market_price=market_price,
        S=100.0,
        K=100.0,
        T=1.0,
        r=0.03,
        q=0.01,
        upper_bound=0.5,
    )

    assert result.converged is False
    assert result.failure_reason is not None
    assert result.failure_reason.startswith("no bracket:")


def test_solver_reports_non_convergence_failure() -> None:
    market_price = bsm_put_price(
        S=100.0,
        K=101.0,
        T=0.9,
        sigma=0.234567,
        r=0.025,
        q=0.005,
    )

    result = solve_implied_volatility(
        option_type=OptionType.PUT,
        market_price=market_price,
        S=100.0,
        K=101.0,
        T=0.9,
        r=0.025,
        q=0.005,
        lower_bound=0.0,
        upper_bound=2.0,
        tolerance=1e-14,
        max_iterations=1,
    )

    assert result.converged is False
    assert result.failure_reason is not None
    assert result.failure_reason.startswith("non-convergence:")
