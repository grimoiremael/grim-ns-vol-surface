from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from volsurface.core.schema import NormalizedOptionQuote, OptionType  # noqa: E402
from volsurface.data_sources.csv_source import read_csv_option_chain  # noqa: E402


def test_csv_source_reads_valid_synthetic_fixture_rows(tmp_path: Path) -> None:
    fixture = tmp_path / "synthetic_chain.csv"
    fixture.write_text(
        "\n".join(
            [
                "underlying,quote_timestamp,expiry,option_type,strike,bid,ask,last,volume,open_interest",
                "SPY,2026-01-02T14:30:00+00:00,2026-02-20T21:00:00+00:00,call,500,12.10,12.40,12.25,100,250",
                "SPY,2026-01-02T14:30:00Z,2026-03-20T21:00:00Z,put,475,6.10,6.40,,0,",
            ]
        ),
        encoding="utf-8",
    )

    result = read_csv_option_chain(fixture, source_name="synthetic-fixture")

    assert result.has_errors is False
    assert result.errors == ()
    assert result.source_path == str(fixture)
    assert result.source_name == "synthetic-fixture"
    assert len(result.quotes) == 2
    assert all(isinstance(quote, NormalizedOptionQuote) for quote in result.quotes)
    assert result.quotes[0].option_type is OptionType.CALL
    assert result.quotes[0].quote_timestamp == datetime(
        2026, 1, 2, 14, 30, tzinfo=timezone.utc
    )
    assert result.quotes[0].source == "synthetic-fixture"
    assert result.quotes[0].metadata["row_number"] == 2
    assert result.quotes[1].option_type is OptionType.PUT
    assert result.quotes[1].last is None
    assert result.quotes[1].volume == 0
    assert result.quotes[1].open_interest is None


def test_csv_source_returns_row_level_errors_and_keeps_valid_rows(tmp_path: Path) -> None:
    fixture = tmp_path / "mixed_chain.csv"
    fixture.write_text(
        "\n".join(
            [
                "underlying,quote_timestamp,expiry,option_type,strike,bid,ask,last,volume,open_interest",
                "SPY,2026-01-02T14:30:00+00:00,2026-02-20T21:00:00+00:00,call,500,12.10,12.40,12.25,100,250",
                "SPY,2026-01-02T14:30:00+00:00,2026-02-20T21:00:00+00:00,straddle,500,12.10,12.40,12.25,100,250",
                "SPY,not-a-date,2026-02-20T21:00:00+00:00,put,500,12.10,12.40,12.25,100,250",
                "SPY,2026-01-02T14:30:00+00:00,2026-02-20T21:00:00+00:00,call,-1,12.10,12.40,12.25,100,250",
            ]
        ),
        encoding="utf-8",
    )

    result = read_csv_option_chain(fixture)

    assert len(result.quotes) == 1
    assert result.quotes[0].strike == 500.0
    assert len(result.errors) == 3
    assert [error.row_number for error in result.errors] == [3, 4, 5]
    assert all(error.code == "ROW_PARSE_ERROR" for error in result.errors)
    assert "option_type must be one of" in result.errors[0].message
    assert "quote_timestamp must be an ISO-8601 datetime" in result.errors[1].message
    assert "strike must be positive" in result.errors[2].message


def test_csv_source_reports_missing_required_columns(tmp_path: Path) -> None:
    fixture = tmp_path / "missing_columns.csv"
    fixture.write_text(
        "\n".join(
            [
                "underlying,expiry,option_type,strike,bid",
                "SPY,2026-02-20T21:00:00+00:00,call,500,12.10",
            ]
        ),
        encoding="utf-8",
    )

    result = read_csv_option_chain(fixture)

    assert result.quotes == ()
    assert len(result.errors) == 1
    assert result.errors[0].row_number == 1
    assert result.errors[0].code == "MISSING_COLUMNS"
    assert "ask" in result.errors[0].message


def test_csv_source_reports_empty_csv(tmp_path: Path) -> None:
    fixture = tmp_path / "empty.csv"
    fixture.write_text("", encoding="utf-8")

    result = read_csv_option_chain(fixture)

    assert result.quotes == ()
    assert len(result.errors) == 1
    assert result.errors[0].code == "EMPTY_CSV"
