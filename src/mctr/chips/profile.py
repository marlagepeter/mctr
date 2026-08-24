"""Point-in-time ChipProfile assembly and historical chip comparisons."""

from datetime import date
from typing import Sequence

import numpy as np
import pandas as pd

from mctr.chips.activity import calculate_effective_tradable_chips, effective_free_float
from mctr.chips.density import (
    build_chip_density,
    calculate_chip_concentration,
    calculate_support_resistance,
    find_core_chip_range,
    find_main_chip_peak,
    normalized_density,
)
from mctr.chips.models import ChipProfile, RestrictedShare, ShareholderHolding
from mctr.config import ChipConfig


def _through(history: pd.DataFrame, as_of_date: date | object | None) -> pd.DataFrame:
    """Return a sorted copy containing observations known at the cutoff."""
    from mctr.models.market_data import validate_ohlcv

    result = validate_ohlcv(history)
    if as_of_date is not None:
        result = result.loc[result.index <= pd.Timestamp(as_of_date)]
    return result


def _daily_densities(
    history: pd.DataFrame,
    free_float: float,
    holdings: Sequence[ShareholderHolding] | None,
    config: ChipConfig,
) -> tuple[list[pd.Timestamp], list[pd.Series]]:
    """Build each daily density using only records through that date."""
    dates: list[pd.Timestamp] = []
    densities: list[pd.Series] = []
    for current_date in history.index:
        current_holdings = [
            record for record in (holdings or ())
            if record.effective_date is None or pd.Timestamp(record.effective_date) <= current_date
        ]
        etc = calculate_effective_tradable_chips(
            free_float, current_holdings, config=config, as_of_date=current_date,
        )
        dates.append(pd.Timestamp(current_date))
        densities.append(build_chip_density(history.loc[:current_date], etc))
    return dates, densities


def _historical_peak(peaks: list[float | None], current_index: int, window: int) -> float | None:
    """Return the peak from exactly ``window`` prior observations."""
    position = current_index - window
    return peaks[position] if position >= 0 else None


def build_chip_profile(
    history: pd.DataFrame,
    free_float: float,
    holdings: Sequence[ShareholderHolding] | None = None,
    restricted_shares: Sequence[RestrictedShare] = (),
    config: ChipConfig = ChipConfig(),
    as_of_date: date | object | None = None,
) -> ChipProfile:
    """Build raw chip features strictly through ``as_of_date``.

    ``restricted_shares`` is accepted as dated source data and passed through the
    free-float boundary; it never reduces the already authoritative free float.
    """
    frame = _through(history, as_of_date)
    if frame.empty:
        raise ValueError("history must contain at least one observation")
    as_of = pd.Timestamp(frame.index[-1])
    as_of_free_float = effective_free_float(free_float, restricted_shares, as_of)
    dates, densities = _daily_densities(frame, as_of_free_float, holdings, config)
    current_index = len(densities) - 1
    current_density = densities[-1]
    current_normalized = normalized_density(current_density)
    etc = calculate_effective_tradable_chips(
        as_of_free_float, holdings, config=config, as_of_date=as_of,
    )
    peak = find_main_chip_peak(current_density)
    core = find_core_chip_range(current_density, config.core_coverage_target)
    concentration_values = calculate_chip_concentration(current_density, core)
    support = calculate_support_resistance(
        current_density, float(frame.iloc[-1]["close"]), config.support_resistance_window_pct,
    )
    peaks = [find_main_chip_peak(density) for density in densities]
    peak_prices = [item.peak_price if item else None for item in peaks]

    def migration(window: int) -> tuple[float | None, float | None]:
        prior = _historical_peak(peak_prices, current_index, window)
        if peak is None or prior is None:
            return None, None
        change = peak.peak_price - prior
        return change, change / window

    migrations = {window: migration(window) for window in config.migration_windows}

    def divergence(window: int) -> float | None:
        if current_index < window:
            return None
        prior_peak = peak_prices[current_index - window]
        prior_close = float(frame.iloc[current_index - window]["close"])
        current_close = float(frame.iloc[current_index]["close"])
        if peak is None or prior_peak is None or prior_close <= 0.0 or prior_peak <= 0.0:
            return None
        price_return = current_close / prior_close - 1.0
        chip_peak_return = peak.peak_price / prior_peak - 1.0
        return price_return - chip_peak_return

    migration_5d = migrations.get(5, (None, None))
    migration_20d = migrations.get(20, (None, None))
    migration_60d = migrations.get(60, (None, None))
    return ChipProfile(
        as_of_date=as_of,
        free_float=etc.free_float,
        active_ratio=etc.active_ratio,
        effective_tradable_chips=etc.effective_tradable_chips,
        confidence=etc.confidence,
        fallback_used=etc.fallback_used,
        peak_price=peak.peak_price if peak else None,
        peak_density=peak.peak_density if peak else None,
        core_lower=core.lower_price if core else None,
        core_upper=core.upper_price if core else None,
        core_coverage=core.coverage if core else None,
        concentration=concentration_values["core_density_share"],
        support_density=support.support_density,
        resistance_density=support.resistance_density,
        migration_5d=migration_5d[0],
        migration_20d=migration_20d[0],
        migration_60d=migration_60d[0],
        migration_velocity_5d=migration_5d[1],
        migration_velocity_20d=migration_20d[1],
        migration_velocity_60d=migration_60d[1],
        divergence_20d=divergence(20),
        divergence_60d=divergence(60),
        density=current_density,
        normalized_density=current_normalized,
    )
