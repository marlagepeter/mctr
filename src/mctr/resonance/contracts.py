"""Market, sector, and resonance extension contracts."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RegimeSnapshot:
    """Point-in-time regime inputs for one market layer."""

    position: float | None = None
    momentum: float | None = None
    trend: float | None = None
    relative_strength: float | None = None
    cycle_position: float | None = None


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
