"""Implied-volatility inversion for Black-Scholes-Merton prices."""

from __future__ import annotations

import math
from collections.abc import Callable
from numbers import Real
from typing import Any

from volsurface.core.bsm import bsm_price
from volsurface.core.schema import IVSolveResult, OptionType

try:  # pragma: no cover - exercised only when scipy is installed locally.
    from scipy.optimize import brentq as _scipy_brentq
except ImportError:  # pragma: no cover - local fallback is covered by tests.
    _scipy_brentq = None


def solve_implied_volatility(
    option_type: OptionType | str,
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    q: float = 0.0,
    lower_bound: float = 1e-8,
    upper_bound: float = 5.0,
    tolerance: float = 1e-8,
    max_iterations: int = 100,
) -> IVSolveResult:
    """Invert a BSM option price into implied volatility."""

    try:
        inputs = _validate_solver_inputs(
            option_type=option_type,
            market_price=market_price,
            S=S,
            K=K,
            T=T,
            r=r,
            q=q,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            tolerance=tolerance,
            max_iterations=max_iterations,
        )
    except (TypeError, ValueError) as exc:
        return _failure(f"invalid inputs: {exc}")

    price_failure = _validate_market_price_against_bounds(inputs)
    if price_failure is not None:
        return price_failure

    option_type = inputs["option_type"]
    market_price = inputs["market_price"]
    lower_bound = inputs["lower_bound"]
    upper_bound = inputs["upper_bound"]
    tolerance = inputs["tolerance"]
    max_iterations = int(inputs["max_iterations"])

    zero_vol_price = bsm_price(
        option_type=option_type,
        S=inputs["S"],
        K=inputs["K"],
        T=inputs["T"],
        sigma=0.0,
        r=inputs["r"],
        q=inputs["q"],
    )
    if _is_close_price(zero_vol_price, market_price, tolerance):
        return IVSolveResult(
            converged=True,
            implied_volatility=0.0,
            iterations=0,
            objective_value=zero_vol_price - market_price,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
        )

    objective = _make_objective(inputs)
    f_lower = objective(lower_bound)
    f_upper = objective(upper_bound)

    if _is_close_price(f_lower, 0.0, tolerance):
        return IVSolveResult(
            converged=True,
            implied_volatility=lower_bound,
            iterations=0,
            objective_value=f_lower,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
        )
    if _is_close_price(f_upper, 0.0, tolerance):
        return IVSolveResult(
            converged=True,
            implied_volatility=upper_bound,
            iterations=0,
            objective_value=f_upper,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
        )
    if f_lower * f_upper > 0.0:
        return _failure(
            "no bracket: market price is not bracketed by the volatility bounds",
            lower_bound=lower_bound,
            upper_bound=upper_bound,
        )

    if _scipy_brentq is not None:
        return _solve_with_scipy(
            objective=objective,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            tolerance=tolerance,
            max_iterations=max_iterations,
        )

    return _solve_with_bisection(
        objective=objective,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        f_lower=f_lower,
        f_upper=f_upper,
        tolerance=tolerance,
        max_iterations=max_iterations,
    )


def _validate_solver_inputs(
    option_type: OptionType | str,
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    q: float,
    lower_bound: float,
    upper_bound: float,
    tolerance: float,
    max_iterations: int,
) -> dict[str, Any]:
    normalized_option_type = _coerce_option_type(option_type)
    values = {
        "option_type": normalized_option_type,
        "market_price": _validate_real("market_price", market_price),
        "S": _validate_real("S", S),
        "K": _validate_real("K", K),
        "T": _validate_real("T", T),
        "r": _validate_real("r", r),
        "q": _validate_real("q", q),
        "lower_bound": _validate_real("lower_bound", lower_bound),
        "upper_bound": _validate_real("upper_bound", upper_bound),
        "tolerance": _validate_real("tolerance", tolerance),
        "max_iterations": _validate_positive_int("max_iterations", max_iterations),
    }
    _require_positive("S", values["S"])
    _require_positive("K", values["K"])
    _require_positive("T", values["T"])
    _require_non_negative("lower_bound", values["lower_bound"])
    _require_positive("upper_bound", values["upper_bound"])
    _require_positive("tolerance", values["tolerance"])
    if values["lower_bound"] >= values["upper_bound"]:
        raise ValueError("lower_bound must be less than upper_bound")
    return values


def _validate_market_price_against_bounds(inputs: dict[str, Any]) -> IVSolveResult | None:
    market_price = inputs["market_price"]
    if market_price < 0.0:
        return _failure("invalid price: market_price must be non-negative")

    discounted_spot = inputs["S"] * math.exp(-inputs["q"] * inputs["T"])
    discounted_strike = inputs["K"] * math.exp(-inputs["r"] * inputs["T"])
    if inputs["option_type"] is OptionType.CALL:
        minimum_price = max(discounted_spot - discounted_strike, 0.0)
        maximum_price = discounted_spot
    else:
        minimum_price = max(discounted_strike - discounted_spot, 0.0)
        maximum_price = discounted_strike

    tolerance = inputs["tolerance"]
    if market_price < minimum_price - tolerance:
        return _failure(
            "invalid price: market_price is below the no-arbitrage lower bound",
            lower_bound=inputs["lower_bound"],
            upper_bound=inputs["upper_bound"],
        )
    if market_price > maximum_price + tolerance:
        return _failure(
            "invalid price: market_price is above the no-arbitrage upper bound",
            lower_bound=inputs["lower_bound"],
            upper_bound=inputs["upper_bound"],
        )
    return None


def _make_objective(inputs: dict[str, Any]) -> Callable[[float], float]:
    def objective(sigma: float) -> float:
        return (
            bsm_price(
                option_type=inputs["option_type"],
                S=inputs["S"],
                K=inputs["K"],
                T=inputs["T"],
                sigma=sigma,
                r=inputs["r"],
                q=inputs["q"],
            )
            - inputs["market_price"]
        )

    return objective


def _solve_with_scipy(
    objective: Callable[[float], float],
    lower_bound: float,
    upper_bound: float,
    tolerance: float,
    max_iterations: int,
) -> IVSolveResult:
    try:
        root, result = _scipy_brentq(
            objective,
            lower_bound,
            upper_bound,
            xtol=tolerance,
            rtol=max(tolerance, 1e-15),
            maxiter=max_iterations,
            full_output=True,
            disp=False,
        )
    except ValueError as exc:
        return _failure(
            f"no bracket: {exc}",
            lower_bound=lower_bound,
            upper_bound=upper_bound,
        )

    objective_value = objective(root)
    if not result.converged:
        return _failure(
            "non-convergence: brentq did not converge within max_iterations",
            iterations=result.iterations,
            objective_value=objective_value,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
        )

    return IVSolveResult(
        converged=True,
        implied_volatility=root,
        iterations=result.iterations,
        objective_value=objective_value,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
    )


def _solve_with_bisection(
    objective: Callable[[float], float],
    lower_bound: float,
    upper_bound: float,
    f_lower: float,
    f_upper: float,
    tolerance: float,
    max_iterations: int,
) -> IVSolveResult:
    low = lower_bound
    high = upper_bound
    last_mid = (low + high) / 2.0
    last_value = objective(last_mid)

    for iteration in range(1, max_iterations + 1):
        mid = (low + high) / 2.0
        f_mid = objective(mid)
        last_mid = mid
        last_value = f_mid

        if _is_close_price(f_mid, 0.0, tolerance) or (high - low) / 2.0 <= tolerance:
            return IVSolveResult(
                converged=True,
                implied_volatility=mid,
                iterations=iteration,
                objective_value=f_mid,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
            )

        if f_lower * f_mid <= 0.0:
            high = mid
            f_upper = f_mid
        else:
            low = mid
            f_lower = f_mid

    del f_upper
    return _failure(
        "non-convergence: bisection did not converge within max_iterations",
        iterations=max_iterations,
        objective_value=last_value,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
    )


def _coerce_option_type(option_type: OptionType | str) -> OptionType:
    if isinstance(option_type, OptionType):
        return option_type
    if isinstance(option_type, str):
        try:
            return OptionType(option_type.strip().lower())
        except ValueError as exc:
            valid_values = ", ".join(member.value for member in OptionType)
            raise ValueError(f"option_type must be one of: {valid_values}") from exc
    raise TypeError("option_type must be an OptionType or string")


def _validate_real(field_name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number")
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        raise ValueError(f"{field_name} must be finite")
    return numeric_value


def _validate_positive_int(field_name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return value


def _require_positive(field_name: str, value: float) -> None:
    if value <= 0.0:
        raise ValueError(f"{field_name} must be positive")


def _require_non_negative(field_name: str, value: float) -> None:
    if value < 0.0:
        raise ValueError(f"{field_name} must be non-negative")


def _is_close_price(left: float, right: float, tolerance: float) -> bool:
    return math.isclose(left, right, abs_tol=tolerance, rel_tol=0.0)


def _failure(
    failure_reason: str,
    iterations: int = 0,
    objective_value: float | None = None,
    lower_bound: float | None = None,
    upper_bound: float | None = None,
) -> IVSolveResult:
    return IVSolveResult(
        converged=False,
        iterations=iterations,
        objective_value=objective_value,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        failure_reason=failure_reason,
    )


__all__ = ["solve_implied_volatility"]
