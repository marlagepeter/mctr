from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mctr.config import BottomConfig
from mctr.scoring import (
    calculate_bottom_engine,
    calculate_chip_score,
    calculate_confirmation_factor,
    calculate_contradiction_factor,
    calculate_exhaustion_score,
    calculate_momentum_reversal_score,
    calculate_position_score,
    calculate_risk_override,
    calculate_risk_reward,
    calculate_structural_bottom_score,
    calculate_trend_transition_score,
)


def cfg() -> BottomConfig:
    return BottomConfig()


def chip(**overrides: float) -> SimpleNamespace:
    values = {"concentration": 0.8, "core_lower": 9.5, "core_upper": 10.5,
              "peak_price": 10.0, "support_density": 0.7, "resistance_density": 0.1,
              "migration_20d": 0.02, "divergence_20d": 0.01}
    values.update(overrides)
    return SimpleNamespace(**values)


def resonance(state: str = "M3 Bottom Transition", strength: float = 0.8, gate: float = 0.8) -> SimpleNamespace:
    return SimpleNamespace(market_state=state, market_gate=gate, resonance_strength=strength)


def momentum(good: bool = True) -> dict[str, float]:
    return {"histogram": 0.5 if good else -0.8, "slope": 0.4 if good else -0.8,
            "divergence": 0.7 if good else 0.1, "velocity": 0.5 if good else -0.8, "kdj": 0.7 if good else 0.1}


def exhaustion(good: bool = True) -> dict[str, float]:
    return {"volume": 0.8 if good else 0.1, "price": 0.8 if good else 0.1,
            "efficiency": 0.7 if good else 0.1, "momentum": 0.8 if good else 0.1}


def percentiles(low: bool = True) -> dict[int, float]:
    return {window: (0.1 + window / 10000 if low else 0.9) for window in (60, 120, 250, 500)}


def test_position_score_is_low_price_only_and_geometric() -> None:
    low = calculate_position_score(percentiles(), cfg())
    high = calculate_position_score(percentiles(False), cfg())
    assert low > high and 0 <= low <= 1
    assert low != pytest.approx(1 - sum(percentiles().values()) / 4)


def test_position_score_requires_all_cycles() -> None:
    with pytest.raises(ValueError):
        calculate_position_score({60: 0.1}, cfg())


def test_chip_score_is_geometric() -> None:
    score = calculate_chip_score(0.8, 0.6, 0.4, cfg())
    assert score == pytest.approx((0.8 ** 0.4 * 0.6 ** 0.35 * 0.4 ** 0.25))


def test_chip_score_bounds() -> None:
    with pytest.raises(ValueError):
        calculate_chip_score(1.1, 0.5, 0.5, cfg())


def test_exhaustion_score_is_separate_from_reversal() -> None:
    score = calculate_exhaustion_score(exhaustion(), cfg())
    reversal = calculate_momentum_reversal_score(momentum(), cfg())
    assert score > 0 and reversal > 0 and score != reversal


def test_momentum_reversal_uses_continuous_features() -> None:
    good = calculate_momentum_reversal_score(momentum(), cfg())
    bad = calculate_momentum_reversal_score(momentum(False), cfg())
    assert good > bad


def test_trend_transition_is_non_ordinal() -> None:
    assert calculate_trend_transition_score("T1_DECLINE_STOPPED", cfg()) > calculate_trend_transition_score("T0_MAIN_DECLINE", cfg())
    assert calculate_trend_transition_score("T6_TREND_BROKEN", cfg()) < calculate_trend_transition_score("T4_ACCELERATION", cfg())
    assert calculate_trend_transition_score("T5_RALLY_EXHAUSTION", cfg()) < calculate_trend_transition_score("T4_ACCELERATION", cfg())


def test_structural_score_excludes_trend_confirmation() -> None:
    values = {"position": 0.8, "chip": 0.7, "exhaustion": 0.7, "momentum": 0.6, "resonance": 0.8}
    score = calculate_structural_bottom_score(values, cfg())
    assert 0 < score < 1


def test_confirmation_factor_is_geometric() -> None:
    base = 0.8 ** 0.6 * 0.5 ** 0.4
    assert calculate_confirmation_factor(0.8, 0.5, cfg()) == pytest.approx(base * (1 - abs(0.8 - 0.5)))


def test_confirmation_requires_momentum_trend_directional_agreement() -> None:
    aligned = calculate_confirmation_factor(0.75, 0.75, cfg())
    mismatched = calculate_confirmation_factor(0.99, 0.10, cfg())
    assert aligned > mismatched


def test_contradiction_penalizes_cheap_acceleration() -> None:
    assert calculate_contradiction_factor(0.9, 0.1, 0.2, "M1 Bear / Decline", -0.2, cfg()) < 1


def test_contradiction_does_not_reward_low_price_alone() -> None:
    assert calculate_contradiction_factor(0.9, 0.1, 0.8, "M1 Bear / Decline", 0.0, cfg()) < 1


def test_risk_r0() -> None:
    result = calculate_risk_override("M3 Bottom Transition", "T1_DECLINE_STOPPED", 0.8, 0.0, momentum(), 0.5, 0.0, cfg())
    assert result.state == "R0" and result.risk_factor == 1


@pytest.mark.parametrize("market, trend, expected", [("M2 Decline Exhaustion", "T1_DECLINE_STOPPED", "R1"), ("M7 Bull Exhaustion", "T1_DECLINE_STOPPED", "R1"), ("M3 Bottom Transition", "T6_TREND_BROKEN", "R2"), ("M0 Extreme Bear", "T1_DECLINE_STOPPED", "R3"), ("M8 Breakdown", "T6_TREND_BROKEN", "R3")])
def test_risk_override_states(market: str, trend: str, expected: str) -> None:
    result = calculate_risk_override(market, trend, 0 if market in {"M0 Extreme Bear", "M8 Breakdown"} else 0.5, 0.0, {}, 0.5, 0.0, cfg())
    assert result.state == expected


def test_risk_override_detects_multiple_conditions() -> None:
    result = calculate_risk_override("M3 Bottom Transition", "T1_DECLINE_STOPPED", 0.8, -0.2, {"slope": -1.0}, 3.0, -0.2, cfg())
    assert result.state == "R2" and len(result.reasons) >= 2


def test_risk_override_factor_order() -> None:
    assert cfg().risk_r3_factor < cfg().risk_r2_factor < cfg().risk_r1_factor < 1


def test_reward_has_zones_not_exact_forecast() -> None:
    history = pd.DataFrame({"high": [10.0, 12.0, 15.0]})
    result = calculate_risk_reward(10.0, chip(core_upper=11.0, peak_price=10.5, support_density=8.0, resistance_density=0.1), history, cfg())
    assert result.target_zone_1 is not None
    assert result.target_zone_1[1] > result.target_zone_1[0]
    assert result.explanation


def test_reward_without_observable_target_is_explicit() -> None:
    result = calculate_risk_reward(10.0, chip(core_upper=9.0, peak_price=9.0, support_density=8.0, resistance_density=0.1), None, cfg())
    assert result.target_zone_1 is None and result.confidence == "low"


def test_scenario_a_strategic_bottom() -> None:
    result = calculate_bottom_engine("2024-01-01", percentiles(), chip_profile=chip(), exhaustion_features=exhaustion(), momentum_features=momentum(), trend_state="T2_REVERSAL_CONFIRMED", resonance=resonance(), current_price=10.0, history=pd.DataFrame({"high": [10, 12, 15]}), config=cfg())
    assert result.bottom_level in {"L3", "L4"} and result.risk_override_state == "R0"


def test_scenario_b_cheap_but_falling() -> None:
    result = calculate_bottom_engine("2024-01-01", percentiles(), chip_profile=chip(concentration=0.1, support_density=0.1, resistance_density=0.8, migration_20d=-0.2), exhaustion_features=exhaustion(False), momentum_features=momentum(False), trend_state="T6_TREND_BROKEN", resonance=resonance("M8 Breakdown", 0.8, 0), current_price=10.0, history=pd.DataFrame({"high": [10, 12]}), config=cfg())
    assert result.bottom_level not in {"L3", "L4"} and result.risk_override_state == "R3"


def test_scenario_c_exhaustion_without_reversal_is_l2() -> None:
    result = calculate_bottom_engine("2024-01-01", percentiles(), chip_profile=chip(), exhaustion_features=exhaustion(), momentum_features=momentum(False), trend_state="T1_DECLINE_STOPPED", resonance=resonance("M2 Decline Exhaustion", 0.4, 0.5), current_price=10.0, history=pd.DataFrame({"high": [10, 12]}), config=cfg())
    assert result.bottom_level == "L2"


def test_scenario_d_reversal_is_l3_or_l4() -> None:
    result = calculate_bottom_engine("2024-01-01", percentiles(), chip_profile=chip(), exhaustion_features=exhaustion(), momentum_features=momentum(), trend_state="T2_REVERSAL_CONFIRMED", resonance=resonance(), current_price=10.0, history=pd.DataFrame({"high": [10, 12, 15]}), config=cfg())
    assert result.bottom_level in {"L3", "L4"}


def test_scenario_e_m8_never_l4() -> None:
    result = calculate_bottom_engine("2024-01-01", percentiles(), chip_profile=chip(), exhaustion_features=exhaustion(), momentum_features=momentum(), trend_state="T2_REVERSAL_CONFIRMED", resonance=resonance("M8 Breakdown", 0.99, 0), current_price=10.0, config=cfg())
    assert result.bottom_level != "L4" and result.risk_override_state == "R3"


def test_scenario_f_sector_mismatch_is_penalized() -> None:
    result = calculate_bottom_engine("2024-01-01", percentiles(), chip_profile=chip(), exhaustion_features=exhaustion(), momentum_features=momentum(), trend_state="T2_REVERSAL_CONFIRMED", resonance=resonance(), current_price=10.0, sector_relative_strength=-0.2, config=cfg())
    assert result.contradiction_factor < 1


def test_scenario_g_high_position_not_l3_l4() -> None:
    result = calculate_bottom_engine("2024-01-01", percentiles(False), chip_profile=chip(), exhaustion_features=exhaustion(), momentum_features=momentum(), trend_state="T3_UPTREND", resonance=resonance(), current_price=10.0, config=cfg())
    assert result.bottom_level not in {"L3", "L4"}


def test_low_trend_does_not_automatically_reject_bottom() -> None:
    result = calculate_bottom_engine("2024-01-01", percentiles(), chip_profile=chip(), exhaustion_features=exhaustion(), momentum_features=momentum(), trend_state="T0_MAIN_DECLINE", resonance=resonance(), current_price=10.0, config=cfg())
    assert result.bottom_probability > 0


def test_result_explanation_and_confidence() -> None:
    result = calculate_bottom_engine("2024-01-01", percentiles(), chip_profile=chip(), exhaustion_features=exhaustion(), momentum_features=momentum(), trend_state="T1_DECLINE_STOPPED", resonance=resonance(), current_price=10.0, config=cfg())
    assert result.explanation["position_reason"] and result.confidence


def test_missing_features_have_explicit_degradation() -> None:
    result = calculate_bottom_engine("2024-01-01", percentiles(), chip_profile=SimpleNamespace(), exhaustion_features={"volume": 0.5, "price": 0.5, "efficiency": 0.5, "momentum": 0.5}, momentum_features={"histogram": 0.5, "slope": 0.5, "divergence": 0.5, "velocity": 0.5, "kdj": 0.5}, trend_state="T1_DECLINE_STOPPED", resonance=resonance(), current_price=10.0, config=cfg())
    assert result.confidence == "medium"


def test_future_price_injection_cannot_change_snapshot() -> None:
    base = pd.DataFrame({"high": [10, 12, 15]})
    extended = pd.concat([base, pd.DataFrame({"high": [1000, 1]})], ignore_index=True)
    first = calculate_risk_reward(10, chip(), base, cfg())
    second = calculate_risk_reward(10, chip(), extended.iloc[:3], cfg())
    assert first == second


def test_probability_is_not_risk_reward() -> None:
    result = calculate_bottom_engine("2024-01-01", percentiles(), chip_profile=chip(), exhaustion_features=exhaustion(), momentum_features=momentum(), trend_state="T2_REVERSAL_CONFIRMED", resonance=resonance(), current_price=10, config=cfg())
    assert result.bottom_probability != result.risk_reward.rr1


def test_phase_two_chip_profile_fields_are_only_read() -> None:
    profile = chip()
    result = calculate_bottom_engine("2024-01-01", percentiles(), profile, exhaustion(), momentum(), "T1_DECLINE_STOPPED", resonance(), 10, config=cfg())
    assert result.chip_score >= 0


def test_near_resistance_has_more_pressure_than_far_resistance() -> None:
    near = SimpleNamespace(concentration=0.8, core_lower=9.8, core_upper=10.2, peak_price=10.0,
                           support_density=0.0, resistance_density=0.8,
                           normalized_density=pd.Series({10.2: 1.0}), migration_20d=0.0)
    far = SimpleNamespace(concentration=0.8, core_lower=9.8, core_upper=10.2, peak_price=10.0,
                          support_density=0.0, resistance_density=0.8,
                          normalized_density=pd.Series({15.0: 1.0}), migration_20d=0.0)
    near_result = calculate_bottom_engine("2024-01-01", percentiles(), near, exhaustion(), momentum(), "T1_DECLINE_STOPPED", resonance(), 10.0, config=cfg())
    far_result = calculate_bottom_engine("2024-01-01", percentiles(), far, exhaustion(), momentum(), "T1_DECLINE_STOPPED", resonance(), 10.0, config=cfg())
    assert near_result.chip_score < far_result.chip_score


def test_near_support_has_more_support_than_far_support() -> None:
    near = SimpleNamespace(concentration=0.8, core_lower=9.8, core_upper=10.2, peak_price=10.0,
                           support_density=0.8, resistance_density=0.0,
                           normalized_density=pd.Series({9.8: 1.0}), migration_20d=0.0)
    far = SimpleNamespace(concentration=0.8, core_lower=9.8, core_upper=10.2, peak_price=10.0,
                          support_density=0.8, resistance_density=0.0,
                          normalized_density=pd.Series({5.0: 1.0}), migration_20d=0.0)
    near_result = calculate_bottom_engine("2024-01-01", percentiles(), near, exhaustion(), momentum(), "T1_DECLINE_STOPPED", resonance(), 10.0, config=cfg())
    far_result = calculate_bottom_engine("2024-01-01", percentiles(), far, exhaustion(), momentum(), "T1_DECLINE_STOPPED", resonance(), 10.0, config=cfg())
    assert near_result.chip_score > far_result.chip_score


def test_momentum_feature_scales_are_configurable() -> None:
    default = calculate_momentum_reversal_score(momentum(), cfg())
    scaled = calculate_momentum_reversal_score(momentum(), BottomConfig(momentum_feature_scales={"histogram": 10.0, "slope": 10.0, "divergence": 10.0, "velocity": 10.0, "kdj": 10.0}))
    assert default != scaled


def test_resonance_is_not_recomputed_by_bottom_engine() -> None:
    class ResonanceSpy:
        resonance_strength = 0.42
        market_state = "M3 Bottom Transition"
        market_gate = 0.8
    result = calculate_bottom_engine("2024-01-01", percentiles(), chip(), exhaustion(), momentum(), "T1_DECLINE_STOPPED", ResonanceSpy(), 10.0, config=cfg())
    assert result.resonance_score == pytest.approx(0.42)


def test_t4_t5_do_not_imply_bottom_and_t6_is_risk() -> None:
    t4 = calculate_bottom_engine("2024-01-01", percentiles(False), chip(), exhaustion(), momentum(), "T4_ACCELERATION", resonance(), 10.0, config=cfg())
    t5 = calculate_bottom_engine("2024-01-01", percentiles(False), chip(), exhaustion(), momentum(), "T5_RALLY_EXHAUSTION", resonance(), 10.0, config=cfg())
    t6 = calculate_bottom_engine("2024-01-01", percentiles(), chip(), exhaustion(), momentum(), "T6_TREND_BROKEN", resonance(), 10.0, config=cfg())
    assert t4.bottom_level not in {"L3", "L4"}
    assert t5.bottom_level not in {"L3", "L4"}
    assert t6.risk_override_state == "R2"


def test_probability_and_risk_reward_are_independent() -> None:
    profile = chip(core_upper=10.5, peak_price=10.2)
    index = pd.DatetimeIndex(["2024-01-01"])
    first = calculate_bottom_engine("2024-01-01", percentiles(), profile, exhaustion(), momentum(), "T2_REVERSAL_CONFIRMED", resonance(), 10.0, history=pd.DataFrame({"high": [10.5]}, index=index), config=cfg())
    second = calculate_bottom_engine("2024-01-01", percentiles(), profile, exhaustion(), momentum(), "T2_REVERSAL_CONFIRMED", resonance(), 10.0, history=pd.DataFrame({"high": [100.0]}, index=index), config=cfg(), history_as_of_date=pd.Timestamp("2024-01-01"))
    assert first.bottom_probability == pytest.approx(second.bottom_probability)
