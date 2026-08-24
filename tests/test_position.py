import numpy as np
import pandas as pd
import pytest

from mctr.position import position_features, rolling_price_position


def test_position_features_are_causal() -> None:
    close = pd.Series([1, 2, 3, 2, 4, 5], dtype=float)
    result = position_features(close, windows=(3,))
    assert result.loc[4, "position_3"] == pytest.approx(1.0)
    changed = close.copy()
    changed.iloc[5] = 1000
    changed_result = position_features(changed, windows=(3,))
    pd.testing.assert_series_equal(result["position_3"].iloc[:5], changed_result["position_3"].iloc[:5])


def test_position_handles_insufficient_history_and_flat_range() -> None:
    result = rolling_price_position(pd.Series([1, 1, 1, 1], dtype=float), 3)
    assert result.iloc[:2].isna().all()
    assert np.isnan(result.iloc[2])
