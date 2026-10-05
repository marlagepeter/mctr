"""Sector regime calculations and data contracts."""

from typing import Optional, Union

from dataclasses import dataclass

from .models import SectorRegimeProfile, SectorRelativeStrengthProfile
from .regime import calculate_sector_regime
from .relative_strength import calculate_relative_strength

@dataclass(frozen=True)
class SectorRegimeInputs:
	"""Backward-compatible input contract retained from Phase 1 scaffolding."""

	sector_name: str
	position: Optional[float] = None
	momentum: Optional[float] = None
	trend: Optional[float] = None
	relative_strength: Optional[float] = None
	cycle_position: Optional[float] = None

__all__ = ["SectorRegimeInputs", "SectorRegimeProfile", "SectorRelativeStrengthProfile", "calculate_relative_strength", "calculate_sector_regime"]
