"""Trend structure features and state classification."""

import pandas as pd

from mctr.models.states import TrendState


def trend_features(close: pd.Series, window: int = 20) -> pd.DataFrame:
    """Build causal trend structure features.

    Moving averages are descriptive features only; state classification uses slope,
    directional efficiency, and momentum inputs rather than crossover rules.
    """
    if window < 2:
        raise ValueError("window must be at least 2")
    mean = close.rolling(window, min_periods=window).mean()
    slope = mean.diff()
    returns = close.pct_change(window)
    efficiency = close.diff(window).abs() / close.diff().abs().rolling(window, min_periods=window).sum()
    return pd.DataFrame({"trend_mean": mean, "trend_mean_slope": slope,
                         "trend_return": returns, "trend_efficiency": efficiency})


def classify_trend(features: pd.DataFrame) -> pd.Series:
    """Classify a trend row-by-row from structure and histogram slope.

    Missing inputs remain unclassified as NA. This is a deliberately small,
    testable baseline for the Trend Engine, not a complete trading strategy.
    """
    required = {"trend_mean_slope", "trend_return", "trend_efficiency", "macd_histogram_slope"}
    missing = required - set(features.columns)
    if missing:
        raise ValueError(f"missing trend inputs: {sorted(missing)}")
    state = pd.Series(pd.NA, index=features.index, dtype="Int64")
    valid = features[list(required)].notna().all(axis=1)
    slope = features["trend_mean_slope"]
    ret = features["trend_return"]
    efficiency = features["trend_efficiency"]
    hist_slope = features["macd_histogram_slope"]
    state.loc[valid & (slope < 0) & (hist_slope < 0)] = TrendState.T0_MAIN_DECLINE
    state.loc[valid & (slope < 0) & (hist_slope >= 0)] = TrendState.T1_DECLINE_STOPPED
    state.loc[valid & (slope >= 0) & (ret <= 0)] = TrendState.T2_REVERSAL_CONFIRMED
    state.loc[valid & (slope >= 0) & (ret > 0) & (efficiency < 0.7)] = TrendState.T3_UPTREND
    state.loc[valid & (slope >= 0) & (ret > 0) & (efficiency >= 0.7) & (hist_slope > 0)] = TrendState.T4_ACCELERATION
    state.loc[valid & (slope >= 0) & (ret > 0) & (efficiency >= 0.7) & (hist_slope <= 0)] = TrendState.T5_RALLY_EXHAUSTION
    state.loc[valid & (slope < 0) & (ret > 0)] = TrendState.T6_TREND_BROKEN
    return state.rename("trend_state")
