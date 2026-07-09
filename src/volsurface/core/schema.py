"""Core schema objects for the Toy Model volatility-surface pipeline."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from numbers import Real
from typing import Any, TypeVar


class OptionType(str, Enum):
    """Supported vanilla option types."""

    CALL = "call"
    PUT = "put"


class AdmissibilitySeverity(str, Enum):
    """Severity for quote admissibility diagnostics."""

    INFO = "info"
    WARNING = "warning"
    REJECT = "reject"


EnumT = TypeVar("EnumT", bound=Enum)


def _coerce_enum(enum_type: type[EnumT], field_name: str, value: Any) -> EnumT:
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        try:
            return enum_type(value.strip().lower())
        except ValueError as exc:
            valid_values = ", ".join(member.value for member in enum_type)
            raise ValueError(
                f"{field_name} must be one of: {valid_values}"
            ) from exc
    raise TypeError(f"{field_name} must be a {enum_type.__name__}")


def _validate_required_text(field_name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")


def _validate_optional_text(field_name: str, value: str | None) -> None:
    if value is None:
        return
    _validate_required_text(field_name, value)


def _validate_datetime(field_name: str, value: datetime | None) -> None:
    if value is None:
        return
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime")


def _validate_expiry_after_quote(
    expiry: datetime, quote_timestamp: datetime | None
) -> None:
    _validate_datetime("expiry", expiry)
    _validate_datetime("quote_timestamp", quote_timestamp)
    if quote_timestamp is None:
        return
    try:
        if expiry <= quote_timestamp:
            raise ValueError("expiry must be after quote_timestamp")
    except TypeError as exc:
        raise ValueError(
            "expiry and quote_timestamp must both be timezone-aware or both naive"
        ) from exc


def _validate_real(field_name: str, value: float | None) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number")
    if not math.isfinite(float(value)):
        raise ValueError(f"{field_name} must be finite")


def _validate_positive(field_name: str, value: float | None) -> None:
    _validate_real(field_name, value)
    if value is None:
        return
    if float(value) <= 0:
        raise ValueError(f"{field_name} must be positive")


def _validate_non_negative(field_name: str, value: float | None) -> None:
    _validate_real(field_name, value)
    if value is None:
        return
    if float(value) < 0:
        raise ValueError(f"{field_name} must be non-negative")


def _validate_non_negative_int(field_name: str, value: int | None) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")


def _validate_metadata(metadata: Mapping[str, Any]) -> None:
    if not isinstance(metadata, Mapping):
        raise TypeError("metadata must be a mapping")
    for key in metadata:
        if not isinstance(key, str):
            raise TypeError("metadata keys must be strings")


@dataclass(frozen=True, slots=True)
class OptionQuote:
    """Raw option quote shape before project-level normalization."""

    underlying: str
    expiry: datetime
    option_type: OptionType
    strike: float
    bid: float | None = None
    ask: float | None = None
    quote_timestamp: datetime | None = None
    last: float | None = None
    volume: int | None = None
    open_interest: int | None = None
    quote_id: str | None = None
    raw_symbol: str | None = None
    source: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "option_type", _coerce_enum(OptionType, "option_type", self.option_type)
        )
        _validate_required_text("underlying", self.underlying)
        _validate_optional_text("quote_id", self.quote_id)
        _validate_optional_text("raw_symbol", self.raw_symbol)
        _validate_optional_text("source", self.source)
        _validate_expiry_after_quote(self.expiry, self.quote_timestamp)
        _validate_positive("strike", self.strike)
        _validate_non_negative("bid", self.bid)
        _validate_non_negative("ask", self.ask)
        _validate_non_negative("last", self.last)
        _validate_non_negative_int("volume", self.volume)
        _validate_non_negative_int("open_interest", self.open_interest)
        _validate_metadata(self.metadata)


@dataclass(frozen=True, slots=True)
class NormalizedOptionQuote:
    """Validated quote shape consumed by admissibility and IV stages."""

    underlying: str
    expiry: datetime
    option_type: OptionType
    strike: float
    bid: float
    ask: float
    quote_timestamp: datetime | None = None
    mid: float | None = None
    last: float | None = None
    volume: int | None = None
    open_interest: int | None = None
    spot: float | None = None
    forward: float | None = None
    risk_free_rate: float | None = None
    dividend_yield: float | None = None
    quote_id: str | None = None
    source_quote_id: str | None = None
    source: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "option_type", _coerce_enum(OptionType, "option_type", self.option_type)
        )
        _validate_required_text("underlying", self.underlying)
        _validate_optional_text("quote_id", self.quote_id)
        _validate_optional_text("source_quote_id", self.source_quote_id)
        _validate_optional_text("source", self.source)
        _validate_expiry_after_quote(self.expiry, self.quote_timestamp)
        _validate_positive("strike", self.strike)
        _validate_non_negative("bid", self.bid)
        _validate_non_negative("ask", self.ask)
        _validate_non_negative("mid", self.mid)
        _validate_non_negative("last", self.last)
        _validate_non_negative_int("volume", self.volume)
        _validate_non_negative_int("open_interest", self.open_interest)
        _validate_positive("spot", self.spot)
        _validate_positive("forward", self.forward)
        _validate_real("risk_free_rate", self.risk_free_rate)
        _validate_real("dividend_yield", self.dividend_yield)
        _validate_metadata(self.metadata)


@dataclass(frozen=True, slots=True)
class AdmissibilityFlag:
    """One admissibility diagnostic attached to a quote."""

    code: str
    message: str
    severity: AdmissibilitySeverity

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "severity",
            _coerce_enum(AdmissibilitySeverity, "severity", self.severity),
        )
        _validate_required_text("code", self.code)
        _validate_required_text("message", self.message)


@dataclass(frozen=True, slots=True)
class AdmissibilityReport:
    """Structured admissibility outcome for a normalized quote."""

    flags: tuple[AdmissibilityFlag, ...] = field(default_factory=tuple)
    quote_id: str | None = None

    def __post_init__(self) -> None:
        _validate_optional_text("quote_id", self.quote_id)
        flags = tuple(self.flags)
        for flag in flags:
            if not isinstance(flag, AdmissibilityFlag):
                raise TypeError("flags must contain AdmissibilityFlag instances")
        object.__setattr__(self, "flags", flags)

    @property
    def is_admissible(self) -> bool:
        return not any(flag.severity is AdmissibilitySeverity.REJECT for flag in self.flags)

    @property
    def has_warnings(self) -> bool:
        return any(flag.severity is AdmissibilitySeverity.WARNING for flag in self.flags)

    @property
    def rejection_reasons(self) -> tuple[str, ...]:
        return tuple(
            flag.message
            for flag in self.flags
            if flag.severity is AdmissibilitySeverity.REJECT
        )

    @property
    def warning_messages(self) -> tuple[str, ...]:
        return tuple(
            flag.message
            for flag in self.flags
            if flag.severity is AdmissibilitySeverity.WARNING
        )


@dataclass(frozen=True, slots=True)
class IVSolveResult:
    """Structured result from an implied-volatility solver."""

    converged: bool
    implied_volatility: float | None = None
    iterations: int = 0
    objective_value: float | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.converged, bool):
            raise TypeError("converged must be a bool")
        _validate_non_negative("implied_volatility", self.implied_volatility)
        _validate_non_negative_int("iterations", self.iterations)
        _validate_real("objective_value", self.objective_value)
        _validate_non_negative("lower_bound", self.lower_bound)
        _validate_non_negative("upper_bound", self.upper_bound)
        _validate_optional_text("failure_reason", self.failure_reason)
        if self.lower_bound is not None and self.upper_bound is not None:
            if float(self.lower_bound) >= float(self.upper_bound):
                raise ValueError("lower_bound must be less than upper_bound")
        if self.converged and self.implied_volatility is None:
            raise ValueError("implied_volatility is required when converged is True")
        if not self.converged and self.failure_reason is None:
            raise ValueError("failure_reason is required when converged is False")


@dataclass(frozen=True, slots=True)
class IVPoint:
    """One solved implied-volatility point ready for surface estimation."""

    underlying: str
    expiry: datetime
    option_type: OptionType
    strike: float
    implied_volatility: float
    quote_timestamp: datetime | None = None
    time_to_expiry_years: float | None = None
    forward: float | None = None
    moneyness: float | None = None
    quote_id: str | None = None
    solve_result: IVSolveResult | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "option_type", _coerce_enum(OptionType, "option_type", self.option_type)
        )
        _validate_required_text("underlying", self.underlying)
        _validate_optional_text("quote_id", self.quote_id)
        _validate_expiry_after_quote(self.expiry, self.quote_timestamp)
        _validate_positive("strike", self.strike)
        _validate_non_negative("implied_volatility", self.implied_volatility)
        _validate_positive("time_to_expiry_years", self.time_to_expiry_years)
        _validate_positive("forward", self.forward)
        _validate_positive("moneyness", self.moneyness)
        if self.solve_result is not None:
            if not isinstance(self.solve_result, IVSolveResult):
                raise TypeError("solve_result must be an IVSolveResult")
            if not self.solve_result.converged:
                raise ValueError("solve_result must be converged for an IVPoint")
        _validate_metadata(self.metadata)


__all__ = [
    "AdmissibilityFlag",
    "AdmissibilityReport",
    "AdmissibilitySeverity",
    "IVPoint",
    "IVSolveResult",
    "NormalizedOptionQuote",
    "OptionQuote",
    "OptionType",
]
