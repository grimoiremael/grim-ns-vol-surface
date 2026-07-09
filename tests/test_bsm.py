from __future__ import annotations

import math
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from volsurface.core.bsm import bsm_call_price, bsm_price, bsm_put_price  # noqa: E402
from volsurface.core.schema import OptionType  # noqa: E402


def test_bsm_call_and_put_prices_are_non_negative() -> None:
    call_price = bsm_call_price(S=100.0, K=105.0, T=0.5, sigma=0.22, r=0.04, q=0.01)
    put_price = bsm_put_price(S=100.0, K=105.0, T=0.5, sigma=0.22, r=0.04, q=0.01)

    assert call_price >= 0.0
    assert put_price >= 0.0


def test_bsm_prices_are_monotonic_in_volatility() -> None:
    low_vol_call = bsm_call_price(S=100.0, K=100.0, T=1.0, sigma=0.15, r=0.03, q=0.01)
    high_vol_call = bsm_call_price(S=100.0, K=100.0, T=1.0, sigma=0.35, r=0.03, q=0.01)
    low_vol_put = bsm_put_price(S=100.0, K=100.0, T=1.0, sigma=0.15, r=0.03, q=0.01)
    high_vol_put = bsm_put_price(S=100.0, K=100.0, T=1.0, sigma=0.35, r=0.03, q=0.01)

    assert high_vol_call > low_vol_call
    assert high_vol_put > low_vol_put


def test_bsm_put_call_parity_with_continuous_dividend_yield() -> None:
    S = 100.0
    K = 97.0
    T = 0.75
    sigma = 0.28
    r = 0.045
    q = 0.012

    call_price = bsm_call_price(S=S, K=K, T=T, sigma=sigma, r=r, q=q)
    put_price = bsm_put_price(S=S, K=K, T=T, sigma=sigma, r=r, q=q)
    parity_value = S * math.exp(-q * T) - K * math.exp(-r * T)

    assert call_price - put_price == pytest.approx(parity_value, abs=1e-10)


def test_bsm_price_dispatches_by_option_type() -> None:
    call_price = bsm_price(
        option_type=OptionType.CALL,
        S=100.0,
        K=100.0,
        T=1.0,
        sigma=0.2,
        r=0.03,
        q=0.01,
    )
    put_price = bsm_price(
        option_type="put",
        S=100.0,
        K=100.0,
        T=1.0,
        sigma=0.2,
        r=0.03,
        q=0.01,
    )

    assert call_price == bsm_call_price(S=100.0, K=100.0, T=1.0, sigma=0.2, r=0.03, q=0.01)
    assert put_price == bsm_put_price(S=100.0, K=100.0, T=1.0, sigma=0.2, r=0.03, q=0.01)


@pytest.mark.parametrize(
    ("field_name", "kwargs", "match"),
    (
        ("S", {"S": 0.0}, "S must be positive"),
        ("K", {"K": -1.0}, "K must be positive"),
        ("T", {"T": -0.01}, "T must be non-negative"),
        ("sigma", {"sigma": -0.01}, "sigma must be non-negative"),
        ("r", {"r": math.inf}, "r must be finite"),
        ("q", {"q": math.nan}, "q must be finite"),
    ),
)
def test_bsm_validates_inputs(
    field_name: str,
    kwargs: dict[str, float],
    match: str,
) -> None:
    del field_name
    valid_kwargs = {
        "S": 100.0,
        "K": 100.0,
        "T": 1.0,
        "sigma": 0.2,
        "r": 0.03,
        "q": 0.01,
    }
    valid_kwargs.update(kwargs)

    with pytest.raises(ValueError, match=match):
        bsm_call_price(**valid_kwargs)


def test_bsm_rejects_invalid_option_type() -> None:
    with pytest.raises(ValueError, match="option_type must be one of"):
        bsm_price(
            option_type="straddle",
            S=100.0,
            K=100.0,
            T=1.0,
            sigma=0.2,
            r=0.03,
            q=0.01,
        )
