"""Pure future-label and grouped validation statistics."""

from typing import Optional, Union

from collections.abc import Sequence

import numpy as np
import pandas as pd

from .models import ValidationObservation

DEFAULT_RETURN_HORIZONS: tuple[int, ...] = (5, 20, 60, 120, 250)
DEFAULT_MFE_MAE_HORIZONS: tuple[int, ...] = (20, 60, 120)

def future_metrics(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    position: int,
    return_horizons: Sequence[int] = DEFAULT_RETURN_HORIZONS,
    excursion_horizons: Sequence[int] = DEFAULT_MFE_MAE_HORIZONS,
) -> dict[str, Optional[float]]:
    """Calculate labels from observations strictly after the signal position.

    ``forward_return_N = close[T+N] / close[T] - 1``. MFE/MAE use T+1 through
    T+N. Insufficient future observations return None; no value is imputed.
    """

    if position < 0 or position >= len(close):
        raise IndexError("position outside close series")
    entry = float(close.iloc[position])
    if not np.isfinite(entry) or entry <= 0.0:
        raise ValueError("signal close must be a positive finite value")
    output: dict[str, Optional[float]] = {}
    for horizon in return_horizons:
        if horizon < 1:
            raise ValueError("horizons must be positive")
        target = position + horizon
        output[f"forward_return_{horizon}d"] = (
            float(close.iloc[target]) / entry - 1.0 if target < len(close) else None
        )
    for horizon in excursion_horizons:
        if horizon < 1:
            raise ValueError("horizons must be positive")
        start, end = position + 1, position + horizon + 1
        if end > len(close):
            output[f"mfe_{horizon}d"] = None
            output[f"mae_{horizon}d"] = None
            continue
        future_high = high.iloc[start:end].dropna()
        future_low = low.iloc[start:end].dropna()
        output[f"mfe_{horizon}d"] = float(future_high.max() / entry - 1.0) if not future_high.empty else None
        output[f"mae_{horizon}d"] = float(future_low.min() / entry - 1.0) if not future_low.empty else None
    return output

def attach_future_labels(
    signals: pd.DataFrame,
    ohlcv: pd.DataFrame,
    symbol: str,
    date_column: str = "date",
) -> pd.DataFrame:
    """Return signal rows enriched with future-only labels for one symbol.

    Signals are matched by date and only rows whose date exists in OHLCV are
    evaluated. OHLCV is sorted and never used to alter the signal columns.
    """
    if signals.empty or ohlcv.empty:
        return signals.copy()
    source = ohlcv.copy()
    if date_column in source.columns:
        source[date_column] = pd.to_datetime(source[date_column])
        source = source.set_index(date_column)
    source.index = pd.to_datetime(source.index)
    source = source.sort_index()
    result = signals.copy()
    if date_column in result.columns:
        result[date_column] = pd.to_datetime(result[date_column])
    result["symbol"] = symbol
    labels: list[dict[str, Optional[float]]] = []
    for date_value in result[date_column]:
        timestamp = pd.Timestamp(date_value)
        if timestamp not in source.index:
            labels.append({})
            continue
        position = source.index.get_loc(timestamp)
        labels.append(future_metrics(source["close"], source["high"], source["low"], position))
    label_frame = pd.DataFrame(labels, index=result.index)
    return pd.concat([result, label_frame], axis=1)

def probability_bucket(probability: Optional[float]) -> Optional[str]:
    """Assign fixed, non-calibrated probability reporting buckets."""
    if probability is None or not np.isfinite(probability):
        return None
    clipped = min(1.0, max(0.0, float(probability)))
    if clipped == 1.0:
        return "0.8-1.0"
    lower = int(clipped * 5) * 2
    return f"{lower / 10:.1f}-{(lower + 2) / 10:.1f}"

def grouped_statistics(observations: pd.DataFrame, group_column: str) -> pd.DataFrame:
    """Summarize sample count, mean/median return, win rate, MFE and MAE."""
    if observations.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for group, group_frame in observations.groupby(group_column, dropna=False):
        for horizon in DEFAULT_RETURN_HORIZONS:
            values = group_frame[f"forward_return_{horizon}d"].dropna()
            mfe = group_frame[f"mfe_{min(horizon, 120)}d"].dropna() if f"mfe_{min(horizon, 120)}d" in group_frame else pd.Series(dtype=float)
            mae = group_frame[f"mae_{min(horizon, 120)}d"].dropna() if f"mae_{min(horizon, 120)}d" in group_frame else pd.Series(dtype=float)
            rows.append({
                group_column: group,
                "horizon": horizon,
                "sample_count": int(values.size),
                "mean_return": float(values.mean()) if not values.empty else np.nan,
                "median_return": float(values.median()) if not values.empty else np.nan,
                "win_rate": float((values > 0).mean()) if not values.empty else np.nan,
                "mean_mfe": float(mfe.mean()) if not mfe.empty else np.nan,
                "mean_mae": float(mae.mean()) if not mae.empty else np.nan,
            })
    return pd.DataFrame(rows)
