"""Black-Scholes-Merton pricing for vanilla European options."""

from __future__ import annotations

import math
from enum import Enum
from numbers import Real
from typing import Any

from volsurface.core.schema import OptionType


_SQRT_TWO = math.sqrt(2.0)


def bsm_call_price(
    S: float,
    K: float,
    T: float,
    sigma: float,
    r: float,
    q: float = 0.0,
) -> float:
    """Price a European call with continuous dividend yield."""

    inputs = _validate_bsm_inputs(S=S, K=K, T=T, sigma=sigma, r=r, q=q)
    if inputs["T"] == 0.0:
        return max(inputs["S"] - inputs["K"], 0.0)
    if inputs["sigma"] == 0.0:
        return _zero_volatility_call_price(**inputs)

    d1, d2 = _d1_d2(**inputs)
    discounted_spot = inputs["S"] * math.exp(-inputs["q"] * inputs["T"])
    discounted_strike = inputs["K"] * math.exp(-inputs["r"] * inputs["T"])
    price = discounted_spot * _normal_cdf(d1) - discounted_strike * _normal_cdf(d2)
    return _clamp_tiny_negative_price(price)


def bsm_put_price(
    S: float,
    K: float,
    T: float,
    sigma: float,
    r: float,
    q: float = 0.0,
) -> float:
    """Price a European put with continuous dividend yield."""

    inputs = _validate_bsm_inputs(S=S, K=K, T=T, sigma=sigma, r=r, q=q)
    if inputs["T"] == 0.0:
        return max(inputs["K"] - inputs["S"], 0.0)
    if inputs["sigma"] == 0.0:
        return _zero_volatility_put_price(**inputs)

    d1, d2 = _d1_d2(**inputs)
    discounted_spot = inputs["S"] * math.exp(-inputs["q"] * inputs["T"])
    discounted_strike = inputs["K"] * math.exp(-inputs["r"] * inputs["T"])
    price = discounted_strike * _normal_cdf(-d2) - discounted_spot * _normal_cdf(-d1)
    return _clamp_tiny_negative_price(price)


def bsm_price(
    option_type: OptionType | str,
    S: float,
    K: float,
    T: float,
    sigma: float,
    r: float,
    q: float = 0.0,
) -> float:
    """Price a European option by option type."""

    normalized_type = _coerce_option_type(option_type)
    if normalized_type is OptionType.CALL:
        return bsm_call_price(S=S, K=K, T=T, sigma=sigma, r=r, q=q)
    return bsm_put_price(S=S, K=K, T=T, sigma=sigma, r=r, q=q)


def _validate_bsm_inputs(
    S: float,
    K: float,
    T: float,
    sigma: float,
    r: float,
    q: float,
) -> dict[str, float]:
    values = {
        "S": _validate_real("S", S),
        "K": _validate_real("K", K),
        "T": _validate_real("T", T),
        "sigma": _validate_real("sigma", sigma),
        "r": _validate_real("r", r),
        "q": _validate_real("q", q),
    }
    _require_positive("S", values["S"])
    _require_positive("K", values["K"])
    _require_non_negative("T", values["T"])
    _require_non_negative("sigma", values["sigma"])
    return values


def _validate_real(field_name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number")
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        raise ValueError(f"{field_name} must be finite")
    return numeric_value


def _require_positive(field_name: str, value: float) -> None:
    if value <= 0.0:
        raise ValueError(f"{field_name} must be positive")


def _require_non_negative(field_name: str, value: float) -> None:
    if value < 0.0:
        raise ValueError(f"{field_name} must be non-negative")


def _coerce_option_type(option_type: OptionType | str) -> OptionType:
    if isinstance(option_type, OptionType):
        return option_type
    if isinstance(option_type, str):
        try:
            return OptionType(option_type.strip().lower())
        except ValueError as exc:
            valid_values = ", ".join(member.value for member in OptionType)
            raise ValueError(f"option_type must be one of: {valid_values}") from exc
    if isinstance(option_type, Enum):
        raise TypeError("option_type must be an OptionType")
    raise TypeError("option_type must be an OptionType or string")


def _normal_cdf(x: float) -> float:
    return 0.5 * math.erfc(-x / _SQRT_TWO)


def _d1_d2(
    S: float,
    K: float,
    T: float,
    sigma: float,
    r: float,
    q: float,
) -> tuple[float, float]:
    sigma_sqrt_t = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / sigma_sqrt_t
    return d1, d1 - sigma_sqrt_t


def _zero_volatility_call_price(
    S: float,
    K: float,
    T: float,
    sigma: float,
    r: float,
    q: float,
) -> float:
    del sigma
    discounted_spot = S * math.exp(-q * T)
    discounted_strike = K * math.exp(-r * T)
    return max(discounted_spot - discounted_strike, 0.0)


def _zero_volatility_put_price(
    S: float,
    K: float,
    T: float,
    sigma: float,
    r: float,
    q: float,
) -> float:
    del sigma
    discounted_spot = S * math.exp(-q * T)
    discounted_strike = K * math.exp(-r * T)
    return max(discounted_strike - discounted_spot, 0.0)


def _clamp_tiny_negative_price(price: float) -> float:
    if price < 0.0 and math.isclose(price, 0.0, abs_tol=1e-12):
        return 0.0
    return price


__all__ = [
    "bsm_call_price",
    "bsm_price",
    "bsm_put_price",
]
