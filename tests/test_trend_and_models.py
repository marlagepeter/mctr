import numpy as np
import pandas as pd

from mctr.chips import EffectiveTradableChips
from mctr.models import TrendState
from mctr.trend import classify_trend, trend_features


def test_trend_classification_uses_structure_and_momentum() -> None:
    close = pd.Series(np.linspace(20, 10, 50))
    features = trend_features(close, window=5)
    features["macd_histogram_slope"] = -1.0
    states = classify_trend(features)
    assert states.dropna().iloc[-1] == TrendState.T0_MAIN_DECLINE


def test_effective_tradable_chips_uses_activity_ratio_once() -> None:
    assert EffectiveTradableChips(free_float=1000, active_ratio=0.35).value == 350
