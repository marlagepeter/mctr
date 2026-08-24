"""Sector regime extension point."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SectorRegimeInputs:
    """Contract for sector position, momentum, trend, and relative strength."""

    sector_name: str
    position: float | None = None
    momentum: float | None = None
    trend: float | None = None
    relative_strength: float | None = None
    cycle_position: float | None = None


# TODO: implement sector aggregation and point-in-time relative strength.
