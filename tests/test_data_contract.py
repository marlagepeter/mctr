import pandas as pd
import pytest

from mctr.data import (
    DataQualityReport,
    HistoricalChipInput,
    MarketDataBundle,
    build_snapshot,
    quality_report,
    validate_free_float,
    validate_market,
    validate_ohlcv,
    validate_sector,
    validate_shareholder,
    validate_stock,
)


def ohlcv(rows: int = 3) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=rows)
    return pd.DataFrame({"date": dates, "open": [1.0] * rows, "high": [2.0] * rows,
                         "low": [1.0] * rows, "close": [1.5] * rows, "volume": [10.0] * rows})


def test_ohlcv_normal_input() -> None:
    result = validate_ohlcv(ohlcv())
    assert isinstance(result.index, pd.DatetimeIndex)
    assert result.index.is_monotonic_increasing


def test_ohlcv_unsorted_is_rejected() -> None:
    frame = ohlcv().iloc[::-1]
    with pytest.raises(ValueError, match="sorted"):
        validate_ohlcv(frame)


def test_ohlcv_duplicate_date_is_rejected() -> None:
    frame = pd.concat([ohlcv(1), ohlcv(1)], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate"):
        validate_ohlcv(frame)


def test_ohlcv_missing_column_is_rejected() -> None:
    with pytest.raises(ValueError, match="missing columns"):
        validate_ohlcv(ohlcv().drop(columns="volume"))


@pytest.mark.parametrize("changes", [
    {"low": [3.0, 1.0, 1.0]},
    {"close": [3.0, 1.5, 1.5]},
    {"volume": [-1.0, 10.0, 10.0]},
])
def test_ohlcv_invalid_values_are_rejected(changes: dict[str, list[float]]) -> None:
    frame = ohlcv()
    for column, values in changes.items():
        frame[column] = values
    with pytest.raises(ValueError, match="invalid|negative"):
        validate_ohlcv(frame)


def test_stock_symbol_date_unique_and_multi_symbol() -> None:
    frame = pd.concat([ohlcv().assign(symbol="A"), ohlcv().assign(symbol="B")], ignore_index=True)
    result = validate_stock(frame)
    assert set(result.symbol) == {"A", "B"}
    duplicate = pd.concat([ohlcv(1).assign(symbol="A"), ohlcv(1).assign(symbol="A")], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate key"):
        validate_stock(duplicate)


def test_sector_date_unique_and_multi_sector() -> None:
    frame = pd.concat([ohlcv().assign(sector="tech"), ohlcv().assign(sector="bank")], ignore_index=True)
    result = validate_sector(frame)
    assert set(result.sector) == {"tech", "bank"}
    duplicate = pd.concat([ohlcv(1).assign(sector="tech"), ohlcv(1).assign(sector="tech")], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate key"):
        validate_sector(duplicate)


def test_market_validation() -> None:
    assert len(validate_market(ohlcv())) == 3


def test_free_float_positive_and_zero_rejected() -> None:
    frame = pd.DataFrame({"date": ["2024-01-01"], "symbol": ["A"], "free_float_shares": [100.0]})
    assert validate_free_float(frame)["free_float_shares"].iloc[0] == 100
    frame.loc[0, "free_float_shares"] = 0
    with pytest.raises(ValueError, match="positive"):
        validate_free_float(frame)


def test_free_float_future_record_is_not_accepted_by_snapshot() -> None:
    frame = pd.DataFrame({"date": ["2024-01-01", "2024-01-03"], "symbol": ["A", "A"], "free_float_shares": [100.0, 200.0]})
    snapshot = build_snapshot("2024-01-02", "A", ohlcv(), free_float=frame)
    assert list(snapshot.free_float["free_float_shares"]) == [100.0]


def test_shareholder_activity_weight_bounds_and_future_data() -> None:
    frame = pd.DataFrame({"effective_date": ["2024-01-01", "2024-01-03"], "symbol": ["A", "A"], "shareholder_id": ["h1", "h2"], "shares": [10.0, 20.0], "holder_type": ["fund", "retail"], "activity_weight": [0.5, 0.8]})
    result = validate_shareholder(frame)
    assert len(result) == 2
    snapshot = build_snapshot("2024-01-02", "A", ohlcv(), shareholders=frame)
    assert list(snapshot.shareholders["shareholder_id"]) == ["h1"]
    frame.loc[0, "activity_weight"] = 1.1
    with pytest.raises(ValueError, match="between"):
        validate_shareholder(frame)


def test_snapshot_filters_stock_market_sector_and_breadth() -> None:
    stock = ohlcv(3).assign(symbol="A")
    market = MarketDataBundle({"sse": ohlcv(3)})
    sector = ohlcv(3).assign(sector="tech")
    breadth = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=3), "advance_count": [1, 1, 1], "decline_count": [1, 1, 1], "unchanged_count": [0, 0, 0], "new_high_count": [0, 0, 0], "new_low_count": [0, 0, 0], "above_ma20_ratio": [0.5] * 3, "above_ma60_ratio": [0.5] * 3, "above_ma120_ratio": [0.5] * 3, "above_ma250_ratio": [0.5] * 3, "total_turnover": [10.0] * 3})
    snapshot = build_snapshot("2024-01-02", "A", stock, market, sector, breadth)
    assert snapshot.stock_ohlcv.index[-1] == pd.Timestamp("2024-01-02")
    assert snapshot.market_data.indices["sse"].index[-1] == pd.Timestamp("2024-01-02")
    assert snapshot.sector_data.index[-1] == pd.Timestamp("2024-01-02")
    assert snapshot.market_data_available and snapshot.sector_data_available


def test_snapshot_missing_chip_is_unavailable() -> None:
    snapshot = build_snapshot("2024-01-01", "A", ohlcv())
    assert snapshot.chip_data_available is False
    assert isinstance(snapshot.chip_input, HistoricalChipInput)


def test_snapshot_future_rows_are_excluded() -> None:
    snapshot = build_snapshot("2024-01-02", "A", ohlcv(3))
    assert snapshot.stock_ohlcv.index.max() == pd.Timestamp("2024-01-02")


def test_quality_report_missing_and_invalid_rows() -> None:
    frame = ohlcv().drop(columns="volume")
    report = quality_report(frame, ("open", "high", "low", "close", "volume"), symbol="A")
    assert isinstance(report, DataQualityReport)
    assert "volume" in report.missing_columns
    frame = ohlcv().drop(index=1)
    report = quality_report(frame, ("open", "high", "low", "close", "volume"), symbol="A")
    assert pd.Timestamp("2024-01-02") in report.missing_dates


def test_quality_report_future_rows() -> None:
    report = quality_report(ohlcv(), ("open", "high", "low", "close", "volume"), as_of_date="2024-01-02")
    assert report.future_rows == (2,)


def test_quality_report_availability_flags() -> None:
    report = quality_report(ohlcv(), ("open", "high", "low", "close", "volume"), symbol="A", chip_data_available=True, market_data_available=True, sector_data_available=False)
    assert report.chip_data_available and report.market_data_available
    assert not report.sector_data_available


def test_stock_requires_symbol() -> None:
    with pytest.raises(ValueError, match="symbol"):
        validate_stock(ohlcv())


def test_sector_requires_sector() -> None:
    with pytest.raises(ValueError, match="sector"):
        validate_sector(ohlcv())


def test_market_index_accepts_datetime_index() -> None:
    frame = ohlcv().set_index("date")
    result = validate_market(frame)
    assert isinstance(result.index, pd.DatetimeIndex)


def test_snapshot_symbol_filters_free_float_and_shareholders() -> None:
    free_float = pd.DataFrame({"date": ["2024-01-01", "2024-01-01"], "symbol": ["A", "B"], "free_float_shares": [100.0, 200.0]})
    shareholders = pd.DataFrame({"effective_date": ["2024-01-01", "2024-01-01"], "symbol": ["A", "B"], "shareholder_id": ["a", "b"], "shares": [10.0, 20.0], "holder_type": ["fund", "fund"], "activity_weight": [0.5, 0.5]})
    snapshot = build_snapshot("2024-01-02", "A", ohlcv(), free_float=free_float, shareholders=shareholders)
    assert set(snapshot.free_float.symbol) == {"A"}
    assert set(snapshot.shareholders.symbol) == {"A"}
