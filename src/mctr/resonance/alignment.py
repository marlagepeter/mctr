"""Directional alignment and market gate functions."""

from typing import Optional, Union

from mctr.config import MarketConfig

def _trend_value(value: object) -> Optional[int]:
    """Normalize trend enum or integer-like values."""

    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def market_gate(market_state: str, market_strength: float, floor: float = 0.15) -> tuple[float, str]:
    """Cap resonance in M0/M8 systemic-risk states."""
    if not 0.0 <= floor <= 1.0:
        raise ValueError("floor must be in [0, 1]")
    if market_state in {"M0 Extreme Bear", "M8 Breakdown"}:
        return 0.0, f"{market_state} is systemic-risk environment"
    if market_state in {"M7 Bull Exhaustion", "M2 Decline Exhaustion"}:
        return min(market_strength, 0.5), f"{market_state} caps environmental participation"
    return max(floor, min(1.0, market_strength)), "market environment does not trigger a hard gate"

def directional_alignment(upper_state: str, lower_state: str, upper_strength: float, lower_strength: float) -> tuple[float, str]:
    """Measure directional agreement between adjacent layers."""
    upper_positive = any(token in upper_state.lower() for token in ("recovery", "bull", "strong", "trend", "transition"))
    lower_positive = any(token in lower_state.lower() for token in ("recovery", "bull", "strong", "trend", "transition"))
    if upper_positive == lower_positive:
        value = 0.5 + 0.5 * min(max(upper_strength, 0.0), max(lower_strength, 0.0))
        return value, f"{upper_state} and {lower_state} have matching direction"
    return 0.2, f"{upper_state} and {lower_state} have conflicting direction"

def _cycle_class(state: str) -> str:
    """Map named cycle states to directional phases, not ordinal scores."""
    value = state.lower()
    if any(token in value for token in ("breakdown", "extreme bear", "extreme weak")):
        return "breakdown"
    if "exhaustion" in value or "weakening" in value:
        return "exhaustion"
    if any(token in value for token in ("bottom transition", "recovery", "reversal", "low-observation")):
        return "transition"
    if any(token in value for token in ("bull", "strong trend", "acceleration", "uptrend")):
        return "up"
    if any(token in value for token in ("bear", "decline", "weak")):
        return "low"
    return "neutral"

def cycle_alignment(upper_state: str, middle_state: str, lower_state: str, config: MarketConfig) -> tuple[float, str]:
    """Combine adjacent phase compatibility with a configured geometric mean."""
    classes = [_cycle_class(value) for value in (upper_state, middle_state, lower_state)]
    scores: list[float] = []
    for left, right in zip(classes, classes[1:]):
        if left == right:
            key = "same"
        elif {left, right} == {"transition", "up"} or {left, right} == {"low", "transition"}:
            key = "progression"
        elif "breakdown" in {left, right}:
            key = "breakdown"
        elif "exhaustion" in {left, right}:
            key = "exhaustion"
        else:
            key = "neutral"
        scores.append(config.cycle_alignment_scores[key])
    value = float((scores[0] * scores[1]) ** 0.5) if scores else 0.0
    return value, f"cycle classes={classes}; adjacent compatibility={scores}"
