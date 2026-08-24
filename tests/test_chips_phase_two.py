from datetime import date

import numpy as np
import pandas as pd
import pytest

from mctr.chips import (
    ChipConfig,
    RestrictedShare,
    ShareholderHolding,
    ShareholderType,
    build_chip_density,
    build_chip_profile,
    calculate_active_ratio,
    calculate_chip_concentration,
    calculate_effective_tradable_chips,
    calculate_effective_turnover,
    calculate_support_resistance,
    effective_free_float,
    find_core_chip_range,
    find_main_chip_peak,
    normalized_density,
)


def history(days: int = 65) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=days, freq="D")
    close = pd.Series(np.linspace(10.0, 20.0, days), index=index)
    return pd.DataFrame({"open": close - 0.2, "high": close + 0.5,
                         "low": close - 0.5, "close": close, "volume": 10.0}, index=index)


def holders() -> list[ShareholderHolding]:
    return [
        ShareholderHolding("retail", 200, 0.2, ShareholderType.RETAIL),
        ShareholderHolding("fund", 300, 0.3, ShareholderType.FUND, is_top10_tradable=True),
    ]


def test_active_ratio_boundary_and_explicit_activity_weight() -> None:
    result = calculate_active_ratio(1000, holders())
    assert 0.0 <= result.active_ratio <= 1.0
    explicit = ShareholderHolding("x", 100, 0.1, activity_weight=0.9)
    assert calculate_active_ratio(100, [explicit]).active_ratio == pytest.approx(0.9)
    with pytest.raises(ValueError):
        ShareholderHolding("bad", 1, 0.1, activity_weight=1.1)


def test_etc_calculation_and_no_double_subtraction() -> None:
    result = calculate_effective_tradable_chips(1000, holders())
    assert result.effective_tradable_chips == pytest.approx(1000 * result.active_ratio)
    restrictions = [RestrictedShare(500, date(2025, 1, 1), source_date=date(2024, 1, 1))]
    assert effective_free_float(1000, restrictions, date(2024, 6, 1)) == 1000


def test_missing_holdings_is_explicit_fallback() -> None:
    result = calculate_active_ratio(1000, None)
    assert result.fallback_used is True
    assert result.confidence == "low"
    assert result.active_ratio == pytest.approx(0.35)


def test_restricted_future_source_does_not_change_past() -> None:
    restrictions = [RestrictedShare(100, date(2024, 3, 1), source_date=date(2024, 2, 1))]
    future = restrictions + [RestrictedShare(900, date(2025, 1, 1), source_date=date(2024, 4, 1))]
    assert effective_free_float(1000, restrictions, date(2024, 3, 1)) == effective_free_float(1000, future, date(2024, 3, 1))


def test_effective_turnover_boundaries() -> None:
    assert calculate_effective_turnover(0, 100) == 0
    assert calculate_effective_turnover(200, 100) == 1
    with pytest.raises(ValueError):
        calculate_effective_turnover(-1, 100)
    with pytest.raises(ValueError):
        calculate_effective_turnover(1, 0)


def test_density_normalizes_and_uses_ohlcv_center() -> None:
    frame = history(2)
    etc = calculate_effective_tradable_chips(100, [], config=ChipConfig(unknown_activity_weight=1.0))
    density = build_chip_density(frame, etc)
    assert density.sum() == pytest.approx(100)
    assert normalized_density(density).sum() == pytest.approx(1)
    assert list(density.index) == pytest.approx([10.0, 20.0])


def test_density_empty_and_invalid_ohlc() -> None:
    etc = calculate_effective_tradable_chips(100, [], config=ChipConfig(unknown_activity_weight=1.0))
    empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    assert build_chip_density(empty, etc).empty
    bad = history(1)
    bad.loc[:, "low"] = bad["close"] + 1
    with pytest.raises(ValueError):
        build_chip_density(bad, etc)


def test_main_peak_and_core_range() -> None:
    density = pd.Series({10.0: 10.0, 11.0: 50.0, 12.0: 40.0})
    peak = find_main_chip_peak(density)
    core = find_core_chip_range(density, 0.7)
    assert peak is not None and peak.peak_price == 11.0
    assert core is not None and core.lower_price == 11.0 and core.upper_price == 12.0
    assert core.coverage == pytest.approx(0.9)


def test_core_range_data_insufficiency_and_concentration() -> None:
    assert find_core_chip_range(pd.Series(dtype=float), 0.7) is None
    with pytest.raises(ValueError):
        find_core_chip_range(pd.Series({1.0: 1.0}), 0)
    density = pd.Series({10.0: 10.0, 11.0: 90.0})
    core = find_core_chip_range(density, 0.7)
    values = calculate_chip_concentration(density, core)
    assert values["core_density_share"] == pytest.approx(0.9)
    assert values["core_range_width_pct"] == pytest.approx(0.0)


def test_support_and_resistance_are_windowed() -> None:
    density = pd.Series({9.5: 20.0, 9.9: 30.0, 10.1: 40.0, 10.5: 10.0})
    result = calculate_support_resistance(density, 10.0, 0.05)
    assert result.immediate_support == 9.9
    assert result.immediate_resistance == 10.1
    assert result.support_density == pytest.approx(0.5)
    assert result.resistance_density == pytest.approx(0.5)


def test_profile_migration_and_divergence_use_past_observations() -> None:
    frame = history(65)
    etc = calculate_effective_tradable_chips(1000, holders())
    profile = build_chip_profile(frame, 1000, holders())
    assert profile.as_of_date == frame.index[-1]
    assert profile.migration_5d is not None
    assert profile.migration_velocity_5d == pytest.approx(profile.migration_5d / 5)
    assert profile.divergence_20d is not None
    changed = frame.copy()
    changed.iloc[-1, changed.columns.get_loc("close")] = 999
    earlier = build_chip_profile(changed, 1000, holders(), as_of_date=frame.index[-2])
    original_earlier = build_chip_profile(frame, 1000, holders(), as_of_date=frame.index[-2])
    assert earlier.peak_price == original_earlier.peak_price
    assert etc.effective_tradable_chips > 0


def test_profile_future_holder_record_is_ignored() -> None:
    frame = history(3)
    base = ShareholderHolding("old", 500, 0.5, ShareholderType.RETAIL, effective_date=frame.index[0])
    future = ShareholderHolding("future", 500, 0.5, ShareholderType.CONTROLLER, effective_date=frame.index[2])
    past = build_chip_profile(frame, 1000, [base, future], as_of_date=frame.index[1])
    direct = build_chip_profile(frame.iloc[:2], 1000, [base], as_of_date=frame.index[1])
    assert past.active_ratio == pytest.approx(direct.active_ratio)


def test_profile_empty_and_insufficient_windows() -> None:
    empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    with pytest.raises(ValueError):
        build_chip_profile(empty, 100)
    short = build_chip_profile(history(2), 100)
    assert short.migration_5d is None
    assert short.divergence_20d is None


def test_holder_type_priors_change_active_ratio() -> None:
    retail = ShareholderHolding("retail", 100, 0.1, ShareholderType.RETAIL)
    controller = ShareholderHolding("controller", 100, 0.1, ShareholderType.CONTROLLER)
    assert calculate_active_ratio(100, [retail]).active_ratio > calculate_active_ratio(100, [controller]).active_ratio


def test_holder_effective_date_filters_future_record() -> None:
    future = ShareholderHolding("future", 100, 0.1, ShareholderType.RETAIL, effective_date=date(2025, 1, 1))
    result = calculate_active_ratio(100, [future], as_of_date=date(2024, 1, 1))
    assert result.fallback_used is True


def test_config_rejects_invalid_core_target() -> None:
    with pytest.raises(ValueError):
        ChipConfig(core_coverage_target=1.1)


def test_single_day_profile_has_no_historical_comparisons() -> None:
    result = build_chip_profile(history(1), 100)
    assert result.peak_price is not None
    assert result.migration_5d is None
    assert result.divergence_60d is None


def test_restriction_unlock_does_not_reduce_authoritative_free_float() -> None:
    restrictions = [RestrictedShare(900, date(2024, 1, 2), source_date=date(2024, 1, 1))]
    assert effective_free_float(1000, restrictions, date(2024, 1, 1)) == 1000


def test_etc_increase_renormalizes_daily_chip_total() -> None:
    frame = history(2)
    first = calculate_effective_tradable_chips(100, [], config=ChipConfig(unknown_activity_weight=0.5))
    second = calculate_effective_tradable_chips(200, [], config=ChipConfig(unknown_activity_weight=0.5))
    density = build_chip_density(frame, first, etc_by_date={frame.index[1]: second})
    assert density.sum() == pytest.approx(second.effective_tradable_chips)
    assert normalized_density(density).sum() == pytest.approx(1)


def test_etc_decrease_renormalizes_daily_chip_total() -> None:
    frame = history(2)
    first = calculate_effective_tradable_chips(200, [], config=ChipConfig(unknown_activity_weight=0.5))
    second = calculate_effective_tradable_chips(100, [], config=ChipConfig(unknown_activity_weight=0.5))
    density = build_chip_density(frame, first, etc_by_date={frame.index[1]: second})
    assert density.sum() == pytest.approx(second.effective_tradable_chips)


def test_turnover_uses_free_float_not_etc() -> None:
    low_etc = calculate_effective_tradable_chips(
        100, [], config=ChipConfig(unknown_activity_weight=0.1),
    )
    high_etc = calculate_effective_tradable_chips(
        100, [], config=ChipConfig(unknown_activity_weight=0.9),
    )
    assert calculate_effective_turnover(20, low_etc.free_float) == pytest.approx(0.2)
    assert calculate_effective_turnover(20, low_etc.free_float) == calculate_effective_turnover(20, high_etc.free_float)


def test_zero_etc_and_zero_raw_total_are_safe() -> None:
    zero_etc = calculate_effective_tradable_chips(
        100, [ShareholderHolding("locked", 100, 1.0, activity_weight=0.0)],
    )
    density = build_chip_density(history(2), zero_etc)
    assert density.sum() == pytest.approx(0)
    assert normalized_density(density).sum() == pytest.approx(0)


def test_free_float_zero_is_rejected() -> None:
    with pytest.raises(ValueError):
        calculate_effective_tradable_chips(0)
