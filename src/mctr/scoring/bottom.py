"""Phase 4 Bottom Engine."""

from typing import Optional, Union

import math
from collections.abc import Mapping

from mctr.config import BottomConfig
from .components import (
    calculate_chip_score,
    calculate_confirmation_factor,
    calculate_exhaustion_score,
    calculate_momentum_reversal_score,
    calculate_position_score,
    calculate_structural_bottom_score,
    calculate_trend_transition_score,
)
from .models import BottomComponentProfile, BottomEngineResult
from .reward import calculate_risk_reward
from .risk import calculate_contradiction_factor, calculate_risk_override

def _clip(value: float) -> float:
    """Clip a component to its declared probability domain."""

    return max(0.0, min(1.0, float(value)))

def _chip_components(profile: object, current_price: float, config: BottomConfig) -> tuple[float, float, float, str]:
    """Derive Phase 2-only stability, support and inverse pressure components."""
    concentration = getattr(profile, "concentration", None)
    lower = getattr(profile, "core_lower", None)
    upper = getattr(profile, "core_upper", None)
    peak = getattr(profile, "peak_price", None)
    migration = getattr(profile, "migration_20d", None)
    support = getattr(profile, "support_density", None)
    resistance = getattr(profile, "resistance_density", None)
    if concentration is None or support is None or resistance is None:
        fallback = config.exhaustion_priors.get("missing", 0.35)
        return fallback, fallback, fallback, "chip data incomplete; conservative Model Prior used"
    width = abs(upper - lower) / max(abs(peak), 1e-12) if lower is not None and upper is not None and peak is not None else config.price_window_pct
    stability = _clip(float(concentration) * math.exp(-width / config.price_window_pct))
    if migration is not None:
        stability = _clip(stability * (0.5 + 0.5 / (1.0 + abs(float(migration)))))
    density = getattr(profile, "normalized_density", None)
    if density is not None and not density.empty:
        distances = (density.index.to_numpy(dtype=float) - current_price) / current_price
        decay = [math.exp(-abs(float(distance)) / config.chip_distance_scale) for distance in distances]
        support_score = _clip(float(sum(weight * factor for price, weight, factor in zip(density.index, density.to_numpy(), decay) if price < current_price)))
        pressure = float(sum(weight * factor for price, weight, factor in zip(density.index, density.to_numpy(), decay) if price > current_price))
        pressure_score = _clip(1.0 - pressure)
    else:
        support_score = _clip(float(support))
        pressure_score = _clip(1.0 - float(resistance))
    return stability, support_score, pressure_score, "Phase 2 density with configurable price-distance decay"

def _risk_features(momentum_features: Mapping[str, float]) -> dict[str, float]:
    """Normalize named existing features into risk-rule inputs."""
    return {key: float(value) for key, value in momentum_features.items() if value is not None}

def calculate_bottom_engine(
    as_of_date: object,
    position_percentiles: Mapping[int, float],
    chip_profile: object,
    exhaustion_features: Mapping[str, float],
    momentum_features: Mapping[str, float],
    trend_state: str,
    resonance: object,
    current_price: float,
    history: Optional[object] = None,
    market_state: Optional[str] = None,
    sector_relative_strength: Optional[float] = None,
    volume_ratio: Optional[float] = None,
    config: BottomConfig = BottomConfig(),
    history_as_of_date: Optional[object] = None,
) -> BottomEngineResult:
    """Calculate point-in-time raw bottom probability and level.

    This is a research score, not a trade signal or position-sizing rule. All
    supplied inputs must already be point-in-time snapshots as of ``as_of_date``.
    """
    position = calculate_position_score(position_percentiles, config)
    stability, support, pressure, chip_reason = _chip_components(chip_profile, current_price, config)
    chip = calculate_chip_score(stability, support, pressure, config)
    exhaustion = calculate_exhaustion_score(exhaustion_features, config)
    momentum = calculate_momentum_reversal_score(momentum_features, config)
    transition = calculate_trend_transition_score(trend_state, config)
    resonance_score = _clip(getattr(resonance, "resonance_strength", resonance if isinstance(resonance, (float, int)) else 0.0))
    structural = calculate_structural_bottom_score({"position": position, "chip": chip, "exhaustion": exhaustion, "momentum": momentum, "resonance": resonance_score}, config)
    confirmation = calculate_confirmation_factor(momentum, transition, config)
    market_name = market_state or getattr(resonance, "market_state", "")
    contradiction = calculate_contradiction_factor(position, momentum, chip, market_name, sector_relative_strength, config)
    risk = calculate_risk_override(market_name, trend_state, getattr(resonance, "market_gate", 1.0), getattr(chip_profile, "migration_20d", None), _risk_features(momentum_features), volume_ratio, sector_relative_strength, config)
    probability = _clip(structural * confirmation * contradiction * risk.risk_factor)
    if position >= config.l1_threshold and chip < config.l2_threshold and exhaustion < config.l2_threshold:
        level = "L1"
    elif position >= config.l1_threshold and chip >= config.l2_threshold and exhaustion >= config.l2_threshold and (momentum < config.l3_threshold or transition < config.l3_threshold):
        level = "L2"
    elif probability >= config.l3_threshold and momentum >= config.l3_threshold and transition >= config.l3_threshold and resonance_score >= config.resonance_minimum:
        level = "L3"
    else:
        level = "L2" if position >= config.l1_threshold and chip >= config.l2_threshold and exhaustion >= config.l2_threshold else "L1" if probability >= config.l1_threshold else "NONE"
    if history is not None and history_as_of_date is not None and hasattr(history, "loc"):
        history = history.loc[:history_as_of_date]
    rr = calculate_risk_reward(current_price, chip_profile, history, config) if history is not None else calculate_risk_reward(current_price, chip_profile, None, config)
    if level == "L3" and probability >= config.l4_threshold and resonance_score >= config.resonance_high and risk.state == "R0" and rr.rr1 is not None and rr.rr1 >= config.rr1_minimum:
        level = "L4"
    reasons = {
        "position_reason": "low percentile is favorable but not sufficient",
        "chip_reason": chip_reason,
        "exhaustion_reason": "continuous exhaustion features aggregated geometrically",
        "momentum_reason": "continuous reversal features aggregated separately from exhaustion",
        "trend_reason": f"{trend_state} is confirmation, not a hard bottom veto",
        "resonance_reason": "Phase 3 resonance used without recomputation",
        "contradiction_reason": f"factor={contradiction:.4f}",
        "risk_override_reason": "; ".join(risk.reasons) or "no configured risk override triggered",
        "risk_reward_reason": rr.explanation,
        "bottom_level_reason": f"state conditions and probability produced {level}",
    }
    confidence = "high" if risk.confidence == "high" and chip_reason.startswith("Phase 2") and all(value is not None for value in exhaustion_features.values()) else "medium"
    return BottomEngineResult(as_of_date, position, chip, exhaustion, momentum, transition, resonance_score, structural, confirmation, contradiction, risk.risk_factor, probability, level, risk.state, risk.reasons, rr, reasons, confidence)
