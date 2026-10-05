from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mctr.config import MarketConfig
from mctr.chips import ShareholderHolding, ShareholderType, calculate_active_ratio, calculate_effective_tradable_chips, calculate_effective_turnover
from mctr.market import calculate_market_breadth, calculate_market_regime, calculate_market_volume
from mctr.resonance import build_stock_regime, calculate_resonance, market_gate
from mctr.resonance.models import ResonanceProfile
from mctr.sector import calculate_relative_strength, calculate_sector_regime


def ohlcv(values: np.ndarray, volume: float = 100.0) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=len(values), freq="D")
    close = pd.Series(values, index=index)
    return pd.DataFrame({"open": close, "high": close + 1, "low": close - 1,
                         "close": close, "volume": volume}, index=index)


def config() -> MarketConfig:
    return MarketConfig(position_windows=(3, 5), relative_strength_windows=(2, 3, 4))


def regimes(market_state: str = "M5 Bull Trend", market_strength: float = 0.9,
            sector_state: str = "S5 Strong Trend", sector_strength: float = 0.9,
            stock_state: str = "recovery", stock_strength: float = 0.9):
    market = SimpleNamespace(as_of_date=pd.Timestamp("2024-03-01"), market_cycle_state=market_state,
                             market_strength=market_strength, confidence="high")
    sector = SimpleNamespace(as_of_date=pd.Timestamp("2024-03-01"), cycle_state=sector_state,
                             sector_strength=sector_strength, confidence="high")
    stock = SimpleNamespace(as_of_date=pd.Timestamp("2024-03-01"), stock_cycle_state=stock_state,
                            stock_strength=stock_strength, confidence="high")
    return market, sector, stock


def test_market_breadth_counts_and_ma_ratios() -> None:
    dates = pd.date_range("2024-01-01", periods=2)
    closes = pd.DataFrame({"a": [1.0, 2.0], "b": [2.0, 1.0], "c": [1.0, 1.0]}, index=dates)
    result = calculate_market_breadth(closes)
    assert result.loc[dates[1], "advance_count"] == 1
    assert result.loc[dates[1], "decline_count"] == 1
    assert result.loc[dates[1], "unchanged_count"] == 1
    assert set(result.columns) >= {"above_ma20_ratio", "above_ma60_ratio", "new_high_count", "new_low_count"}


def test_market_position_momentum_trend_and_volume() -> None:
    values = np.linspace(10, 30, 45)
    frame = ohlcv(values)
    profile = calculate_market_regime({"benchmark": frame}, config=config())
    volume = calculate_market_volume(frame)
    index = profile.index_profiles["benchmark"]
    assert set(index.position) == {3, 5}
    assert index.macd is not None and index.trend_state is not None
    assert volume.total_market_volume == 100
    assert profile.market_strength >= 0


def test_market_missing_layers_degrade_confidence() -> None:
    profile = calculate_market_regime({"benchmark": ohlcv(np.linspace(10, 30, 45))}, config=config())
    assert profile.breadth_state == "missing"
    assert profile.volume_state == "missing"
    assert profile.confidence == "low"


def test_market_point_in_time_ignores_future_extreme() -> None:
    base = ohlcv(np.linspace(10, 30, 45))
    future = ohlcv(np.concatenate([np.linspace(10, 30, 45), [10000, 1]]))
    cutoff = base.index[-1]
    first = calculate_market_regime({"benchmark": base}, as_of_date=cutoff, config=config())
    second = calculate_market_regime({"benchmark": future}, as_of_date=cutoff, config=config())
    assert first.market_strength == pytest.approx(second.market_strength)
    assert first.market_cycle_state == second.market_cycle_state


def test_sector_relative_strength_definition_and_point_in_time() -> None:
    index = pd.date_range("2024-01-01", periods=6)
    sector = pd.Series([10, 11, 12, 13, 14, 15], index=index, dtype=float)
    market = pd.Series([10, 10, 10, 10, 10, 10], index=index, dtype=float)
    result = calculate_relative_strength(sector, market, windows=(2, 4), as_of_date=index[4])
    assert result.index[-1] == index[4]
    assert result.loc[index[4], "relative_strength_2d"] == pytest.approx(14 / 12 - 1)
    changed = sector.copy()
    changed.iloc[-1] = 9999
    pd.testing.assert_frame_equal(result, calculate_relative_strength(changed, market, (2, 4), index[4]))


def test_sector_position_momentum_trend_and_cycle() -> None:
    values = np.linspace(10, 30, 45)
    market = pd.Series(np.linspace(10, 20, 45), index=pd.date_range("2024-01-01", periods=45))
    profile = calculate_sector_regime("technology", ohlcv(values), market, config=config())
    assert set(profile.position) == {3, 5}
    assert profile.macd_histogram_slope is not None
    assert profile.trend_state is not None
    assert profile.cycle_state.startswith("S")
    assert 0 <= profile.sector_strength <= 1


def test_sector_missing_and_empty_data_are_explicit() -> None:
    market = pd.Series(np.ones(3), index=pd.date_range("2024-01-01", periods=3))
    with pytest.raises(ValueError):
        calculate_sector_regime("empty", pd.DataFrame(), market, config=config())
    with pytest.raises(ValueError):
        calculate_relative_strength(pd.Series(dtype=float), market)


def test_stock_regime_integrates_chip_profile_fields() -> None:
    chip = SimpleNamespace(concentration=0.7, support_density=0.4, resistance_density=0.2,
                           divergence_20d=0.1)
    stock = build_stock_regime(pd.Timestamp("2024-01-01"), "low", "improving", "T2_REVERSAL_CONFIRMED", chip)
    assert stock.chip_state == "supportive"
    assert stock.stock_cycle_state == "recovery"
    assert 0 <= stock.stock_strength <= 1


def test_market_gate_blocks_systemic_risk() -> None:
    gate, reason = market_gate("M0 Extreme Bear", 0.99)
    assert gate == 0
    assert "systemic-risk" in reason
    gate, _ = market_gate("M5 Bull Trend", 0.8)
    assert gate == pytest.approx(0.8)


def test_resonance_a_grade_for_three_aligned_layers() -> None:
    market, sector, stock = regimes()
    result = calculate_resonance(market, sector, stock)
    assert result.resonance_grade == "A"
    assert result.market_gate > 0 and result.sector_alignment > 0 and result.stock_alignment > 0


def test_resonance_b_and_c_grades_are_not_simple_average() -> None:
    market, sector, stock = regimes(market_strength=0.8, sector_strength=0.3, stock_strength=0.95)
    result_b = calculate_resonance(market, sector, stock)
    assert result_b.resonance_grade in {"B", "C", "NONE"}
    market, sector, stock = regimes("M4 Recovery", 0.5, "S4 Recovery", 0.7, "recovery", 0.7)
    result_c = calculate_resonance(market, sector, stock)
    assert result_c.resonance_grade in {"B", "C"}
    assert result_c.resonance_strength != pytest.approx((0.5 + 0.7 + 0.7) / 3)


def test_resonance_d_for_high_market_and_local_stock_case() -> None:
    market, sector, stock = regimes("M7 Bull Exhaustion", 0.8, "S1 Weak", 0.25, "low-observation", 0.8)
    result = calculate_resonance(market, sector, stock)
    assert result.resonance_grade in {"D", "NONE"}
    assert result.resonance_grade != "A"


def test_resonance_none_for_extreme_bear() -> None:
    market, sector, stock = regimes("M0 Extreme Bear", 0.9, "S5 Strong Trend", 0.95, "recovery", 0.95)
    result = calculate_resonance(market, sector, stock)
    assert result.resonance_grade == "NONE"
    assert result.resonance_strength == 0


def test_weakest_link_constrains_strength() -> None:
    strong = calculate_resonance(*regimes())
    weak = calculate_resonance(*regimes(stock_strength=0.1))
    assert weak.weakest_link_factor < strong.weakest_link_factor
    assert weak.resonance_strength < strong.resonance_strength


def test_resonance_explanations_and_confidence() -> None:
    result = calculate_resonance(*regimes())
    assert result.market_gate_reason
    assert result.sector_alignment_reason
    assert result.stock_alignment_reason
    assert result.weakest_link_reason
    assert result.confidence == "high"


def test_no_future_shift_or_backfill_in_phase_three_sources() -> None:
    import pathlib
    source = "\n".join(path.read_text() for path in pathlib.Path("src/mctr/market").glob("*.py"))
    source += "\n" + "\n".join(path.read_text() for path in pathlib.Path("src/mctr/sector").glob("*.py"))
    source += "\n" + "\n".join(path.read_text() for path in pathlib.Path("src/mctr/resonance").glob("*.py"))
    assert "shift(-" not in source
    assert "bfill" not in source
    assert "backfill" not in source


def test_market_breadth_as_of_date_excludes_future_rows() -> None:
    dates = pd.date_range("2024-01-01", periods=3)
    closes = pd.DataFrame({"a": [1, 2, 100], "b": [1, 1, 1]}, index=dates, dtype=float)
    result = calculate_market_breadth(closes, dates[1])
    assert result.index[-1] == dates[1]
    assert result.loc[dates[1], "advance_count"] == 1


def test_market_breadth_empty_input_is_rejected() -> None:
    with pytest.raises(ValueError):
        calculate_market_breadth(pd.DataFrame())


def test_market_volume_amount_and_acceleration_fields() -> None:
    frame = ohlcv(np.linspace(10, 30, 25)).assign(amount=1000.0)
    profile = calculate_market_volume(frame)
    assert profile.total_market_amount == 1000
    assert profile.volume_acceleration is not None


def test_market_accepts_multiple_index_profiles() -> None:
    frame = ohlcv(np.linspace(10, 30, 45))
    profile = calculate_market_regime({"sse": frame, "csi300": frame * 1.1}, config=config())
    assert set(profile.index_profiles) == {"sse", "csi300"}


def test_market_config_rejects_invalid_resonance_weights() -> None:
    with pytest.raises(ValueError):
        MarketConfig(resonance_weights={"market": 1.0, "sector": 1.0, "stock": 1.0})


def test_market_cycle_state_is_explainable() -> None:
    profile = calculate_market_regime({"benchmark": ohlcv(np.linspace(30, 10, 45))}, config=config())
    assert profile.market_cycle_state.startswith("M")
    assert "trend=" in profile.explanation and "position=" in profile.explanation


def test_relative_strength_supports_all_requested_windows() -> None:
    index = pd.date_range("2024-01-01", periods=125)
    values = pd.Series(np.linspace(10, 20, 125), index=index)
    result = calculate_relative_strength(values * 1.1, values, (20, 60, 120))
    assert set(result.columns) == {"relative_strength_20d", "relative_strength_60d", "relative_strength_120d"}


def test_relative_strength_rejects_disjoint_series() -> None:
    left = pd.Series([1.0], index=pd.date_range("2024-01-01", periods=1))
    right = pd.Series([1.0], index=pd.date_range("2025-01-01", periods=1))
    with pytest.raises(ValueError):
        calculate_relative_strength(left, right)


def test_sector_as_of_date_ignores_future_market_change() -> None:
    frame = ohlcv(np.linspace(10, 30, 45))
    market = pd.Series(np.linspace(10, 20, 45), index=frame.index)
    changed = pd.concat([market, pd.Series([9999], index=[frame.index[-1] + pd.Timedelta(days=1)])])
    first = calculate_sector_regime("x", frame, market, as_of_date=frame.index[-1], config=config())
    second = calculate_sector_regime("x", frame, changed, as_of_date=frame.index[-1], config=config())
    assert first.sector_strength == pytest.approx(second.sector_strength)


def test_alignment_penalizes_conflicting_directions() -> None:
    from mctr.resonance import directional_alignment
    value, reason = directional_alignment("M5 Bull Trend", "S1 Weak", 0.9, 0.9)
    assert value == pytest.approx(0.2)
    assert "conflicting" in reason


def test_market_gate_caps_exhaustion() -> None:
    value, _ = market_gate("M7 Bull Exhaustion", 0.9)
    assert value == pytest.approx(0.5)


def test_stock_resistant_chip_state_is_visible() -> None:
    chip = SimpleNamespace(concentration=0.4, support_density=0.1, resistance_density=0.5, divergence_20d=-0.1)
    profile = build_stock_regime(pd.Timestamp("2024-01-01"), "high", "weakening", "T5_RALLY_EXHAUSTION", chip)
    assert profile.chip_state == "resistant"


def test_resonance_custom_weights_are_applied() -> None:
    market, sector, stock = regimes()
    custom = MarketConfig(resonance_weights={"market": 0.6, "sector": 0.2, "stock": 0.2})
    result = calculate_resonance(market, sector, stock, custom)
    assert 0 <= result.resonance_strength <= 1


def test_resonance_with_low_layer_is_below_balanced_case() -> None:
    balanced = calculate_resonance(*regimes())
    constrained = calculate_resonance(*regimes(sector_strength=0.05))
    assert constrained.resonance_strength < balanced.resonance_strength


def test_sector_strength_exposes_four_non_average_components() -> None:
    frame = ohlcv(np.linspace(10, 30, 45))
    market = pd.Series(np.linspace(10, 20, 45), index=frame.index)
    profile = calculate_sector_regime("x", frame, market, config=config())
    assert profile.momentum_strength != profile.position_strength or profile.position_strength != profile.trend_strength
    assert profile.sector_strength != pytest.approx((profile.position_strength + profile.momentum_strength + profile.trend_strength + profile.relative_strength_strength) / 4)


def test_stock_strength_accepts_continuous_inputs_and_is_geometric() -> None:
    chip = SimpleNamespace(concentration=0.8, support_density=0.6, resistance_density=0.2, migration_20d=0.02, divergence_20d=0.01)
    profile = build_stock_regime(pd.Timestamp("2024-01-01"), "neutral", "neutral", "T2_REVERSAL_CONFIRMED", chip,
                                 position_profile={60: 0.5, 120: 0.5}, momentum_features={"macd_histogram": 0.2},
                                 trend_features={"trend_strength": 0.55})
    assert profile.confidence == "high"
    assert profile.stock_strength == pytest.approx((profile.position_strength * profile.momentum_strength * profile.trend_strength * profile.chip_structural_strength) ** 0.25)


def test_trend_state_strength_is_non_ordinal_and_configured() -> None:
    cfg = MarketConfig()
    assert cfg.trend_state_strengths["T6_TREND_BROKEN"] < cfg.trend_state_strengths["T4_ACCELERATION"]
    assert cfg.trend_state_strengths["T5_RALLY_EXHAUSTION"] < cfg.trend_state_strengths["T4_ACCELERATION"]
    assert cfg.trend_state_strengths["T2_REVERSAL_CONFIRMED"] > cfg.trend_state_strengths["T1_DECLINE_STOPPED"]


def test_cycle_alignment_rewards_bottom_transition_chain() -> None:
    from mctr.resonance import cycle_alignment
    value, reason = cycle_alignment("M3 Bottom Transition", "S3 Bottom Transition", "recovery", MarketConfig())
    assert value >= MarketConfig().cycle_alignment_threshold
    assert "transition" in reason


@pytest.mark.parametrize("state, expected", [
    ("M0 Extreme Bear", 0.0), ("M1 Bear / Decline", 0.7), ("M2 Decline Exhaustion", 0.5),
    ("M3 Bottom Transition", 0.7), ("M4 Recovery", 0.7), ("M5 Bull Trend", 0.7),
    ("M6 Acceleration", 0.7), ("M7 Bull Exhaustion", 0.5), ("M8 Breakdown", 0.0),
])
def test_market_gate_complete_mapping(state: str, expected: float) -> None:
    value, _ = market_gate(state, 0.7)
    assert value == pytest.approx(expected)


def test_phase_two_activity_regression_is_unchanged() -> None:
    holder = ShareholderHolding("fund", 300, 0.3, ShareholderType.FUND)
    active = calculate_active_ratio(1000, [holder])
    etc = calculate_effective_tradable_chips(1000, [holder])
    assert active.active_ratio == pytest.approx(0.41)
    assert etc.effective_tradable_chips == pytest.approx(410)
    assert calculate_effective_turnover(100, 1000) == pytest.approx(0.1)


def test_bottom_transition_does_not_require_high_strength_for_cycle_alignment() -> None:
    market, sector, stock = regimes("M3 Bottom Transition", 0.25, "S3 Bottom Transition", 0.25, "recovery", 0.25)
    result = calculate_resonance(market, sector, stock)
    assert result.cycle_alignment >= MarketConfig().cycle_alignment_threshold
    assert result.resonance_strength > 0


def test_m4_neutral_recovery_cannot_be_a_grade() -> None:
    market, sector, stock = regimes("M4 Recovery", 0.9, "S4 Recovery", 0.9, "recovery", 0.9)
    assert calculate_resonance(market, sector, stock).resonance_grade != "A"
