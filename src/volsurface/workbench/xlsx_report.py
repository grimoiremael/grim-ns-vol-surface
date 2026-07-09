"""XLSX workbench reports for operator review."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from volsurface.core.schema import NormalizedOptionQuote, OptionType


NORMALIZED_QUOTES_SHEET = "Normalized Quotes"
NORMALIZED_QUOTE_HEADERS = (
    "underlying",
    "quote_timestamp",
    "expiry",
    "option_type",
    "strike",
    "bid",
    "ask",
    "mid",
    "last",
    "volume",
    "open_interest",
    "spot",
    "forward",
    "risk_free_rate",
    "dividend_yield",
    "quote_id",
    "source_quote_id",
    "source",
    "metadata",
)


def export_normalized_quotes_xlsx(
    quotes: Iterable[NormalizedOptionQuote],
    path: str | Path,
) -> Path:
    """Export normalized quotes to an XLSX workbook for operator review."""

    quote_tuple = tuple(quotes)
    for quote in quote_tuple:
        if not isinstance(quote, NormalizedOptionQuote):
            raise TypeError("quotes must contain NormalizedOptionQuote instances")

    output_path = Path(path)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = NORMALIZED_QUOTES_SHEET
    worksheet.append(NORMALIZED_QUOTE_HEADERS)

    for quote in quote_tuple:
        worksheet.append(_quote_row(quote))

    worksheet.freeze_panes = "A2"
    for column_cells in worksheet.columns:
        header = column_cells[0].value
        if isinstance(header, str):
            worksheet.column_dimensions[column_cells[0].column_letter].width = min(
                max(len(header) + 2, 12),
                36,
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)
    workbook.close()
    return output_path


def _quote_row(quote: NormalizedOptionQuote) -> list[Any]:
    return [
        quote.underlying,
        _datetime_cell(quote.quote_timestamp),
        _datetime_cell(quote.expiry),
        _option_type_cell(quote.option_type),
        quote.strike,
        quote.bid,
        quote.ask,
        quote.mid,
        quote.last,
        quote.volume,
        quote.open_interest,
        quote.spot,
        quote.forward,
        quote.risk_free_rate,
        quote.dividend_yield,
        quote.quote_id,
        quote.source_quote_id,
        quote.source,
        _metadata_cell(quote.metadata),
    ]


def _datetime_cell(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _option_type_cell(value: OptionType | str) -> str:
    if isinstance(value, OptionType):
        return value.value
    return str(value)


def _metadata_cell(metadata: Mapping[str, Any]) -> str:
    if not metadata:
        return ""
    return json.dumps(dict(metadata), sort_keys=True, default=str)


__all__ = [
    "NORMALIZED_QUOTE_HEADERS",
    "NORMALIZED_QUOTES_SHEET",
    "export_normalized_quotes_xlsx",
]
