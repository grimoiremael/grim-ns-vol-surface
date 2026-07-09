from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from volsurface.core.schema import NormalizedOptionQuote, OptionType  # noqa: E402
from volsurface.data_sources.xlsx_source import read_xlsx_option_chain  # noqa: E402


HEADERS = [
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
]


def _save_workbook(path: Path, rows: list[list[object]]) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Chain"
    worksheet.append(HEADERS)
    for row in rows:
        worksheet.append(row)
    workbook.save(path)
    workbook.close()


def test_xlsx_source_reads_valid_synthetic_fixture_rows(tmp_path: Path) -> None:
    fixture = tmp_path / "synthetic_chain.xlsx"
    _save_workbook(
        fixture,
        [
            [
                "SPY",
                datetime(2026, 1, 2, 14, 30),
                datetime(2026, 2, 20, 21, 0),
                "call",
                500,
                12.10,
                12.40,
                12.25,
                100,
                250,
            ],
            [
                "SPY",
                "2026-01-02T14:30:00+00:00",
                "2026-03-20T21:00:00+00:00",
                "put",
                "475",
                "6.10",
                "6.40",
                None,
                0,
                None,
            ],
        ],
    )

    result = read_xlsx_option_chain(
        fixture,
        worksheet_name="Chain",
        source_name="synthetic-xlsx",
    )

    assert result.has_errors is False
    assert result.errors == ()
    assert result.source_path == str(fixture)
    assert result.source_name == "synthetic-xlsx"
    assert result.worksheet_name == "Chain"
    assert len(result.quotes) == 2
    assert all(isinstance(quote, NormalizedOptionQuote) for quote in result.quotes)
    assert result.quotes[0].option_type is OptionType.CALL
    assert result.quotes[0].quote_timestamp == datetime(2026, 1, 2, 14, 30)
    assert result.quotes[0].source == "synthetic-xlsx"
    assert result.quotes[0].metadata["row_number"] == 2
    assert result.quotes[1].option_type is OptionType.PUT
    assert result.quotes[1].last is None
    assert result.quotes[1].volume == 0
    assert result.quotes[1].open_interest is None


def test_xlsx_source_returns_row_level_errors_and_keeps_valid_rows(tmp_path: Path) -> None:
    fixture = tmp_path / "mixed_chain.xlsx"
    _save_workbook(
        fixture,
        [
            [
                "SPY",
                "2026-01-02T14:30:00+00:00",
                "2026-02-20T21:00:00+00:00",
                "call",
                500,
                12.10,
                12.40,
                12.25,
                100,
                250,
            ],
            [
                "SPY",
                "2026-01-02T14:30:00+00:00",
                "2026-02-20T21:00:00+00:00",
                "straddle",
                500,
                12.10,
                12.40,
                12.25,
                100,
                250,
            ],
            [
                "SPY",
                "not-a-date",
                "2026-02-20T21:00:00+00:00",
                "put",
                500,
                12.10,
                12.40,
                12.25,
                100,
                250,
            ],
            [
                "SPY",
                "2026-01-02T14:30:00+00:00",
                "2026-02-20T21:00:00+00:00",
                "call",
                -1,
                12.10,
                12.40,
                12.25,
                100,
                250,
            ],
        ],
    )

    result = read_xlsx_option_chain(fixture, worksheet_name="Chain")

    assert len(result.quotes) == 1
    assert result.quotes[0].strike == 500.0
    assert len(result.errors) == 3
    assert [error.row_number for error in result.errors] == [3, 4, 5]
    assert all(error.code == "ROW_PARSE_ERROR" for error in result.errors)
    assert "option_type must be one of" in result.errors[0].message
    assert "quote_timestamp must be an ISO-8601 datetime" in result.errors[1].message
    assert "strike must be positive" in result.errors[2].message


def test_xlsx_source_reports_missing_required_columns(tmp_path: Path) -> None:
    fixture = tmp_path / "missing_columns.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["underlying", "expiry", "option_type", "strike", "bid"])
    worksheet.append(["SPY", "2026-02-20T21:00:00+00:00", "call", 500, 12.10])
    workbook.save(fixture)
    workbook.close()

    result = read_xlsx_option_chain(fixture)

    assert result.quotes == ()
    assert len(result.errors) == 1
    assert result.errors[0].row_number == 1
    assert result.errors[0].code == "MISSING_COLUMNS"
    assert "ask" in result.errors[0].message
