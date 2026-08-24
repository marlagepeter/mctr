import pandas as pd
import pytest

from mctr.models import validate_ohlcv


def test_validate_ohlcv_sorts_and_rejects_duplicates() -> None:
    frame = pd.DataFrame({
        "date": ["2024-01-02", "2024-01-01"],
        "open": [2, 1], "high": [3, 2], "low": [1, 0],
        "close": [2, 1], "volume": [10, 20],
    })
    result = validate_ohlcv(frame)
    assert result.index.is_monotonic_increasing
    assert result.iloc[0]["close"] == 1


def test_validate_ohlcv_requires_columns() -> None:
    with pytest.raises(ValueError, match="missing columns"):
        validate_ohlcv(pd.DataFrame({"close": [1]}))
