"""CSV fixture ingestion for local option-chain data."""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from volsurface.core.schema import NormalizedOptionQuote, OptionType


SUPPORTED_COLUMNS = frozenset(
    {
        "underlying",
        "quote_timestamp",
        "expiry",
        "option_type",
        "strike",
        "bid",
        "ask",
        "last",
        "volume",
        "open_interest",
    }
)
REQUIRED_COLUMNS = frozenset(
    {
        "underlying",
        "expiry",
        "option_type",
        "strike",
        "bid",
        "ask",
    }
)


@dataclass(frozen=True, slots=True)
class CsvRowError:
    """Row-level CSV ingestion failure."""

    row_number: int
    code: str
    message: str
    raw_row: Mapping[str, str | None] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CsvIngestionResult:
    """Structured result from reading a CSV option-chain fixture."""

    quotes: tuple[NormalizedOptionQuote, ...]
    errors: tuple[CsvRowError, ...]
    source_path: str
    source_name: str

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


def read_csv_option_chain(
    path: str | Path,
    *,
    source_name: str | None = None,
) -> CsvIngestionResult:
    """Read a local CSV fixture into normalized option quotes."""

    source_path = Path(path)
    resolved_source_name = source_name or source_path.name
    quotes: list[NormalizedOptionQuote] = []
    errors: list[CsvRowError] = []

    with source_path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = tuple(reader.fieldnames or ())
        missing_columns = sorted(REQUIRED_COLUMNS.difference(fieldnames))
        if not fieldnames:
            return CsvIngestionResult(
                quotes=(),
                errors=(
                    CsvRowError(
                        row_number=0,
                        code="EMPTY_CSV",
                        message="CSV file does not contain a header row.",
                    ),
                ),
                source_path=str(source_path),
                source_name=resolved_source_name,
            )
        if missing_columns:
            return CsvIngestionResult(
                quotes=(),
                errors=(
                    CsvRowError(
                        row_number=1,
                        code="MISSING_COLUMNS",
                        message=(
                            "CSV file is missing required columns: "
                            + ", ".join(missing_columns)
                            + "."
                        ),
                    ),
                ),
                source_path=str(source_path),
                source_name=resolved_source_name,
            )

        for row_number, row in enumerate(reader, start=2):
            raw_row = _clean_raw_row(row)
            try:
                quotes.append(
                    _parse_quote_row(
                        row=raw_row,
                        row_number=row_number,
                        source_path=source_path,
                        source_name=resolved_source_name,
                    )
                )
            except (TypeError, ValueError) as exc:
                errors.append(
                    CsvRowError(
                        row_number=row_number,
                        code="ROW_PARSE_ERROR",
                        message=str(exc),
                        raw_row=raw_row,
                    )
                )

    return CsvIngestionResult(
        quotes=tuple(quotes),
        errors=tuple(errors),
        source_path=str(source_path),
        source_name=resolved_source_name,
    )


def load_csv_option_chain(
    path: str | Path,
    *,
    source_name: str | None = None,
) -> CsvIngestionResult:
    """Alias for callers that prefer loader naming."""

    return read_csv_option_chain(path, source_name=source_name)


def _parse_quote_row(
    *,
    row: Mapping[str, str | None],
    row_number: int,
    source_path: Path,
    source_name: str,
) -> NormalizedOptionQuote:
    return NormalizedOptionQuote(
        underlying=_required_text(row, "underlying"),
        quote_timestamp=_optional_datetime(row, "quote_timestamp"),
        expiry=_required_datetime(row, "expiry"),
        option_type=_parse_option_type(row),
        strike=_required_float(row, "strike"),
        bid=_required_float(row, "bid"),
        ask=_required_float(row, "ask"),
        last=_optional_float(row, "last"),
        volume=_optional_int(row, "volume"),
        open_interest=_optional_int(row, "open_interest"),
        source=source_name,
        metadata={
            "source_path": str(source_path),
            "source_name": source_name,
            "row_number": row_number,
        },
    )


def _clean_raw_row(row: Mapping[str, Any]) -> dict[str, str | None]:
    cleaned: dict[str, str | None] = {}
    for key, value in row.items():
        if key is None:
            continue
        cleaned[str(key)] = None if value is None else str(value)
    return cleaned


def _parse_option_type(row: Mapping[str, str | None]) -> OptionType:
    raw_value = _required_text(row, "option_type").lower()
    try:
        return OptionType(raw_value)
    except ValueError as exc:
        valid_values = ", ".join(member.value for member in OptionType)
        raise ValueError(f"option_type must be one of: {valid_values}") from exc


def _required_text(row: Mapping[str, str | None], column: str) -> str:
    value = _cell(row, column)
    if value is None or not value.strip():
        raise ValueError(f"{column} is required")
    return value.strip()


def _optional_text(row: Mapping[str, str | None], column: str) -> str | None:
    value = _cell(row, column)
    if value is None or not value.strip():
        return None
    return value.strip()


def _required_datetime(row: Mapping[str, str | None], column: str) -> datetime:
    value = _required_text(row, column)
    return _parse_datetime_value(column, value)


def _optional_datetime(row: Mapping[str, str | None], column: str) -> datetime | None:
    value = _optional_text(row, column)
    if value is None:
        return None
    return _parse_datetime_value(column, value)


def _parse_datetime_value(column: str, value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{column} must be an ISO-8601 datetime") from exc


def _required_float(row: Mapping[str, str | None], column: str) -> float:
    value = _required_text(row, column)
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{column} must be a number") from exc


def _optional_float(row: Mapping[str, str | None], column: str) -> float | None:
    value = _optional_text(row, column)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{column} must be a number") from exc


def _optional_int(row: Mapping[str, str | None], column: str) -> int | None:
    value = _optional_text(row, column)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        try:
            numeric_value = float(value)
        except ValueError as exc:
            raise ValueError(f"{column} must be an integer") from exc
        if not numeric_value.is_integer():
            raise ValueError(f"{column} must be an integer")
        return int(numeric_value)


def _cell(row: Mapping[str, str | None], column: str) -> str | None:
    return row.get(column)


__all__ = [
    "CsvIngestionResult",
    "CsvRowError",
    "REQUIRED_COLUMNS",
    "SUPPORTED_COLUMNS",
    "load_csv_option_chain",
    "read_csv_option_chain",
]
