"""Point-in-time chip density and price-level feature calculations."""

from dataclasses import dataclass
from datetime import date
from typing import Mapping

import numpy as np
import pandas as pd

from mctr.chips.models import EffectiveTradableChipsResult
from mctr.models.market_data import validate_ohlcv


@dataclass(frozen=True)
class MainChipPeak:
    """Price level with the greatest chip share."""

    peak_price: float
    peak_density: float
    peak_index: int


@dataclass(frozen=True)
class CoreChipRange:
    """Tightest contiguous price interval reaching a target chip coverage."""

    lower_price: float
    upper_price: float
    coverage: float
    concentration: float


@dataclass(frozen=True)
class SupportResistance:
    """Density and weighted price levels around the current price."""

    immediate_support: float | None
    support_density: float
    weighted_support: float | None
    immediate_resistance: float | None
    resistance_density: float
    weighted_resistance: float | None


def estimate_price_center(row: pd.Series) -> float:
    """Estimate traded price as ``(high + low + 2 * close) / 4`` from OHLCV.

    This is an OHLCV approximation, not a substitute for tick or intraday data.
    """
    high, low, close = float(row["high"]), float(row["low"]), float(row["close"])
    if low > high or not low <= close <= high:
        raise ValueError("OHLC prices must satisfy low <= close <= high")
    return (high + low + 2.0 * close) / 4.0


def calculate_effective_turnover(volume: float, free_float: float) -> float:
    """Calculate clipped market turnover ``volume / FreeFloat`` in [0, 1]."""
    if volume < 0.0:
        raise ValueError("volume must be non-negative")
    if free_float <= 0.0:
        raise ValueError("free_float must be positive")
    return min(max(volume / free_float, 0.0), 1.0)


def _history_through(history: pd.DataFrame, as_of_date: date | object | None) -> pd.DataFrame:
    """Validate and truncate history to the point-in-time cutoff."""
    result = validate_ohlcv(history)
    if as_of_date is not None:
        result = result.loc[result.index <= pd.Timestamp(as_of_date)]
    return result


def build_chip_density(
    history: pd.DataFrame,
    etc: EffectiveTradableChipsResult,
    as_of_date: date | object | None = None,
    etc_by_date: Mapping[pd.Timestamp, EffectiveTradableChipsResult] | None = None,
) -> pd.Series:
    """Build shares-at-price density by causal daily migration.

    At each date, existing chips decay by ``1 - turnover`` and new chips of
    ``turnover * ETC`` are added at the OHLCV price center. The raw result is
    then scaled to the current day's ETC when its total is positive. ``turnover``
    is market turnover, ``volume / FreeFloat``; ETC only controls migration size.
    """
    frame = _history_through(history, as_of_date)
    density: dict[float, float] = {}
    for _, row in frame.iterrows():
        current_date = pd.Timestamp(row.name)
        current_etc = etc_by_date.get(current_date, etc) if etc_by_date else etc
        turnover = calculate_effective_turnover(float(row["volume"]), current_etc.free_float)
        for price in tuple(density):
            density[price] *= 1.0 - turnover
        center = estimate_price_center(row)
        density[center] = density.get(center, 0.0) + turnover * current_etc.effective_tradable_chips
        raw_total = sum(density.values())
        if raw_total > 0.0:
            scale_factor = current_etc.effective_tradable_chips / raw_total
            for price in tuple(density):
                density[price] *= scale_factor
    return pd.Series(density, dtype=float).sort_index()


def normalized_density(density: pd.Series) -> pd.Series:
    """Normalize shares density to sum to one, preserving an empty result."""
    total = float(density.sum())
    if total <= 0.0:
        return pd.Series(dtype=float, index=density.index, name="normalized_density")
    return (density / total).rename("normalized_density")


def find_main_chip_peak(density: pd.Series) -> MainChipPeak | None:
    """Select the price index with maximum raw chip density."""
    if density.empty:
        return None
    position = int(np.argmax(density.to_numpy()))
    return MainChipPeak(float(density.index[position]), float(density.iloc[position]), position)


def find_core_chip_range(density: pd.Series, target_coverage: float = 0.70) -> CoreChipRange | None:
    """Find the narrowest sorted-price interval covering the target mass.

    The algorithm uses a two-pointer window over price levels and the normalized
    density mass; it never expands a window using future observations.
    """
    if not 0.0 < target_coverage <= 1.0:
        raise ValueError("target_coverage must be in (0, 1]")
    if density.empty or density.sum() <= 0.0:
        return None
    prices = density.sort_index().index.to_numpy(dtype=float)
    masses = normalized_density(density.sort_index()).to_numpy()
    best: tuple[float, int, int, float] | None = None
    right = 0
    mass = 0.0
    for left in range(len(prices)):
        while right < len(prices) and mass < target_coverage:
            mass += masses[right]
            right += 1
        if mass >= target_coverage:
            candidate = (prices[right - 1] - prices[left], left, right - 1, mass)
            if best is None or candidate[0] < best[0]:
                best = candidate
        mass -= masses[left]
    if best is None:
        return None
    _, left, right, coverage = best
    return CoreChipRange(float(prices[left]), float(prices[right]), float(coverage), float(coverage))


def calculate_chip_concentration(
    density: pd.Series,
    core_range: CoreChipRange | None,
) -> dict[str, float]:
    """Return core width as price percentage and core density share."""
    if core_range is None or density.empty:
        return {"core_range_width_pct": np.nan, "core_density_share": np.nan}
    core_share = float(density.loc[core_range.lower_price:core_range.upper_price].sum() / density.sum())
    midpoint = (core_range.lower_price + core_range.upper_price) / 2.0
    width_pct = (core_range.upper_price - core_range.lower_price) / midpoint if midpoint else np.nan
    return {"core_range_width_pct": float(width_pct), "core_density_share": core_share}


def calculate_support_resistance(
    density: pd.Series,
    current_price: float,
    window_pct: float = 0.10,
) -> SupportResistance:
    """Measure normalized chips within configurable +/- percentage windows.

    Immediate levels are the nearest occupied prices; weighted levels are the
    density-weighted mean prices within each side's window.
    """
    if current_price <= 0.0 or window_pct <= 0.0:
        raise ValueError("current_price and window_pct must be positive")
    normalized = normalized_density(density)
    lower, upper = current_price * (1.0 - window_pct), current_price * (1.0 + window_pct)
    below = normalized[(normalized.index < current_price) & (normalized.index >= lower)]
    above = normalized[(normalized.index > current_price) & (normalized.index <= upper)]

    def weighted(values: pd.Series) -> float | None:
        return float((values.index.to_numpy(dtype=float) * values.to_numpy()).sum() / values.sum()) if not values.empty else None

    return SupportResistance(
        immediate_support=float(below.index.max()) if not below.empty else None,
        support_density=float(below.sum()),
        weighted_support=weighted(below),
        immediate_resistance=float(above.index.min()) if not above.empty else None,
        resistance_density=float(above.sum()),
        weighted_resistance=weighted(above),
    )
