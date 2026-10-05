"""Pure Phase 4 component scores."""

import math
from collections.abc import Mapping

from mctr.config import BottomConfig


def geometric(values: Mapping[str, float], weights: Mapping[str, float]) -> float:
    """Return weighted geometric mean, excluding no dimensions silently."""
    if set(values) != set(weights):
        raise ValueError("values and weights must have identical keys")
    if any(not 0.0 <= value <= 1.0 for value in values.values()):
        raise ValueError("component values must be in [0, 1]")
    return math.exp(sum(weights[key] * math.log(max(value, 1e-12)) for key, value in values.items()))


def calculate_position_score(percentiles: Mapping[int, float], config: BottomConfig) -> float:
    """Calculate P = 1 - weighted geometric percentile; low position is favorable."""
    required = {60, 120, 250, 500}
    if set(percentiles) != required:
        raise ValueError("position percentiles must contain 60, 120, 250, 500")
    values = {str(window): max(0.0, min(1.0, float(value))) for window, value in percentiles.items()}
    return max(0.0, min(1.0, 1.0 - geometric(values, config.position_weights)))


def calculate_chip_score(stability: float, support: float, pressure: float, config: BottomConfig) -> float:
    """Combine Phase 2 chip stability, support and inverse pressure geometrically."""
    return geometric({"stability": stability, "support": support, "pressure": pressure}, config.chip_weights)


def calculate_exhaustion_score(features: Mapping[str, float], config: BottomConfig) -> float:
    """Combine continuous exhaustion subcomponents geometrically."""
    return geometric(dict(features), config.exhaustion_weights)


def calculate_momentum_reversal_score(features: Mapping[str, float], config: BottomConfig) -> float:
    """Combine existing MACD/KDJ/divergence/velocity reversal evidence.

    Inputs may be raw signed features; a bounded tanh transform makes their
    direction explicit before geometric aggregation.
    """
    if set(features) != set(config.momentum_weights):
        raise ValueError("momentum features must match configured momentum weights")
    bounded = {
        key: 0.5 + 0.5 * math.tanh(float(value) / config.momentum_feature_scales[key])
        for key, value in features.items()
    }
    return geometric(bounded, config.momentum_weights)


def calculate_trend_transition_score(state: str, config: BottomConfig) -> float:
    """Map T0-T6 to non-ordinal transition priors; T6 is explicitly weak."""
    return float(config.trend_state_priors.get(state, config.trend_state_priors.get(state.upper(), 0.0)))


def calculate_structural_bottom_score(components: Mapping[str, float], config: BottomConfig) -> float:
    """Calculate Bs from P, C, E, M and R using a weighted geometric product."""
    return geometric(dict(components), config.structural_weights)


def calculate_confirmation_factor(momentum: float, trend: float, config: BottomConfig) -> float:
    """Measure momentum/trend agreement, not momentum magnitude alone.

    The agreement term is ``1 - abs(M - T)``. This prevents a strong momentum
    value from confirming a still-unimproved trend by itself.
    """
    agreement = 1.0 - abs(momentum - trend)
    return geometric({"momentum": momentum, "trend": trend}, config.confirmation_weights) * max(0.0, agreement)
