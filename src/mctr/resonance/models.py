"""Three-layer resonance data contracts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class StockRegimeProfile:
    """Point-in-time integration of existing stock and chip features."""

    as_of_date: object
    position_state: str
    momentum_state: str
    trend_state: str
    chip_state: str
    structural_strength: float
    position_strength: float
    momentum_strength: float
    trend_strength: float
    chip_structural_strength: float
    stock_cycle_state: str
    stock_strength: float
    confidence: str
    explanation: str


@dataclass(frozen=True)
class ResonanceProfile:
    """Explainable Market -> Sector -> Stock resonance output."""

    as_of_date: object
    market_state: str
    sector_state: str
    stock_state: str
    market_gate_reason: str
    sector_alignment_reason: str
    stock_alignment_reason: str
    weakest_link_reason: str
    resonance_grade: str
    structural_resonance: float
    cycle_alignment: float
    resonance_strength: float
    market_gate: float
    sector_alignment: float
    stock_alignment: float
    weakest_link_factor: float
    confidence: str
