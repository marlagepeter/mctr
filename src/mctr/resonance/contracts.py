"""Market, sector, and resonance extension contracts."""

from typing import Optional, Protocol, Union

from dataclasses import dataclass

@dataclass(frozen=True)
class RegimeSnapshot:
    """Point-in-time regime inputs for one market layer."""

    position: Optional[float] = None
    momentum: Optional[float] = None
    trend: Optional[float] = None
    relative_strength: Optional[float] = None
    cycle_position: Optional[float] = None

@dataclass(frozen=True)
class ResonanceResult:
    """Nonlinear resonance result contract, pending calibrated implementation."""

    grade: str
    score: float
    layers: tuple[str, ...]

class ResonanceEngine(Protocol):
    """Protocol for Market -> Sector -> Stock resonance."""

    def evaluate(self, market: RegimeSnapshot, sector: RegimeSnapshot,
                 stock: RegimeSnapshot) -> ResonanceResult:
        """Evaluate layered resonance without simple averaging."""
