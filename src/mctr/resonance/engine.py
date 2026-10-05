"""Nonlinear three-layer resonance engine."""

from typing import Optional, Union

import math
from collections.abc import Mapping

from mctr.config import MarketConfig
from mctr.models.states import TrendState
from .alignment import cycle_alignment, directional_alignment, market_gate
from .models import ResonanceProfile, StockRegimeProfile

def _geometric(values: Mapping[str, float], weights: Mapping[str, float]) -> float:
    """Calculate a weighted geometric mean over continuous strengths."""

    total_weight = sum(weights.values())
    if total_weight <= 0.0:
        raise ValueError("strength weights must have positive total")
    return math.exp(sum(weights[key] * math.log(max(1e-12, min(1.0, values[key]))) for key in values) / total_weight)

def _continuous_position(values: list[float], config: MarketConfig) -> float:
    """Convert historical position to distance from neutral, not trend strength."""
    if not values:
        return config.stock_state_priors["neutral"]
    mean = sum(values) / len(values)
    denominator = max(config.position_neutral_center, 1.0 - config.position_neutral_center)
    return max(0.0, min(1.0, 1.0 - abs(mean - config.position_neutral_center) / denominator))

def build_stock_regime(
    as_of_date: object,
    position_state: str,
    momentum_state: str,
    trend_state: object,
    chip_profile: object,
    position_profile: Optional[Mapping[int, float]] = None,
    momentum_features: Optional[Mapping[str, float]] = None,
    trend_features: Optional[Mapping[str, float]] = None,
    config: MarketConfig = MarketConfig(),
) -> StockRegimeProfile:
    """Integrate continuous existing features without producing a trade score.

    Phase 2 ChipProfile values are the only chip inputs. State priors are explicit
    configured fallbacks when continuous feature mappings are unavailable.
    """
    trend_name = str(getattr(trend_state, "name", trend_state))
    position_values = [float(value) for value in (position_profile or {}).values()]
    position_strength = _continuous_position(position_values, config)
    if not position_values:
        position_strength = config.stock_state_priors.get(position_state, config.stock_state_priors["neutral"])
    momentum_values = [float(value) for value in (momentum_features or {}).values() if value is not None and math.isfinite(float(value))]
    if momentum_values:
        momentum_strength = math.prod(0.5 + 0.5 * math.tanh(value / config.momentum_scale) for value in momentum_values) ** (1 / len(momentum_values))
    else:
        momentum_strength = config.stock_state_priors.get(momentum_state, config.stock_state_priors["neutral"])
    trend_strength = float((trend_features or {}).get("trend_strength", config.trend_state_strengths.get(trend_name, config.stock_state_priors["neutral"])))
    concentration = getattr(chip_profile, "concentration", None)
    support = getattr(chip_profile, "support_density", None)
    resistance = getattr(chip_profile, "resistance_density", None)
    migration = getattr(chip_profile, "migration_20d", None)
    divergence = getattr(chip_profile, "divergence_20d", None)
    chip_values = [float(value) for value in (
        concentration,
        support / (support + resistance) if support is not None and resistance is not None and support + resistance > 0 else None,
        0.5 + 0.5 * math.tanh(float(migration) / config.momentum_scale) if migration is not None else None,
        0.5 + 0.5 * math.tanh(float(divergence) / config.chip_divergence_scale) if divergence is not None else None,
    ) if value is not None and math.isfinite(float(value))]
    chip_state = "missing" if not chip_values else "supportive" if support is not None and resistance is not None and support >= resistance else "resistant"
    chip_strength = math.prod(max(0.0, min(1.0, value)) for value in chip_values) ** (1 / len(chip_values)) if chip_values else config.chip_state_priors["missing"]
    components = {
        "position": max(0.0, min(1.0, position_strength)),
        "momentum": max(0.0, min(1.0, momentum_strength)),
        "trend": max(0.0, min(1.0, trend_strength)),
        "chip": chip_strength,
    }
    strength = _geometric(components, config.stock_strength_weights)
    cycle = "recovery" if trend_name in {"T2_REVERSAL_CONFIRMED", "T3_UPTREND", "T4_ACCELERATION"} else "low-observation" if position_state == "low" else "neutral"
    confidence = "high" if position_values and momentum_values and trend_features and chip_values else "medium" if chip_state != "missing" else "low"
    return StockRegimeProfile(
        as_of_date=as_of_date, position_state=position_state, momentum_state=momentum_state,
        trend_state=trend_name.lower(), chip_state=chip_state,
        structural_strength=strength, position_strength=components["position"], momentum_strength=components["momentum"],
        trend_strength=components["trend"], chip_structural_strength=components["chip"],
        stock_cycle_state=cycle, stock_strength=strength, confidence=confidence,
        explanation=f"position={position_state}; momentum={momentum_state}; trend={trend_name}; chip={chip_state}",
    )

def calculate_resonance(market: object, sector: object, stock: StockRegimeProfile, config: MarketConfig = MarketConfig()) -> ResonanceProfile:
    """Calculate structural resonance times cycle alignment, gate, and weakest link."""
    gate, gate_reason = market_gate(market.market_cycle_state, market.market_strength, config.market_gate_floor)
    sector_alignment, sector_reason = directional_alignment(market.market_cycle_state, sector.cycle_state, market.market_strength, sector.sector_strength)
    stock_alignment, stock_reason = directional_alignment(sector.cycle_state, stock.stock_cycle_state, sector.sector_strength, stock.stock_strength)
    cycle_factor, cycle_reason = cycle_alignment(market.market_cycle_state, sector.cycle_state, stock.stock_cycle_state, config)
    weights = config.resonance_weights
    base = market.market_strength ** weights["market"] * sector.sector_strength ** weights["sector"] * stock.stock_strength ** weights["stock"]
    structural = max(0.0, min(1.0, base * sector_alignment * stock_alignment))
    weakest = min(market.market_strength, sector.sector_strength, stock.stock_strength)
    weakest_factor = weakest ** config.weakest_link_exponent
    strength = max(0.0, min(1.0, structural * cycle_factor * gate * weakest_factor))
    if gate == 0.0:
        grade = "NONE"
    elif cycle_factor >= config.cycle_alignment_threshold and strength >= config.grade_c_threshold and market.market_cycle_state in config.grade_a_market_states and sector.cycle_state in config.grade_a_sector_states:
        grade = "A"
    elif strength >= config.grade_b_threshold:
        grade = "B"
    elif strength >= config.grade_c_threshold:
        grade = "C"
    elif "high" in market.market_cycle_state.lower() or "exhaustion" in market.market_cycle_state.lower():
        grade = "D"
    else:
        grade = "NONE"
    return ResonanceProfile(
        as_of_date=max(market.as_of_date, sector.as_of_date, stock.as_of_date), market_state=market.market_cycle_state,
        sector_state=sector.cycle_state, stock_state=stock.stock_cycle_state, market_gate_reason=gate_reason,
        sector_alignment_reason=sector_reason, stock_alignment_reason=f"{stock_reason}; {cycle_reason}",
        weakest_link_reason=f"weakest strength={weakest:.4f}; exponent={config.weakest_link_exponent}", resonance_grade=grade,
        structural_resonance=structural, cycle_alignment=cycle_factor, resonance_strength=strength, market_gate=gate,
        sector_alignment=sector_alignment, stock_alignment=stock_alignment, weakest_link_factor=weakest_factor,
        confidence="high" if market.confidence == sector.confidence == stock.confidence == "high" else "medium",
    )
