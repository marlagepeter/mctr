"""Compatibility namespace for future chip model contracts."""

from mctr.chips.models import (
	ActiveRatioResult,
	ChipProfile,
	ChipSnapshot,
	EffectiveTradableChips,
	EffectiveTradableChipsResult,
	HolderActivity,
	RestrictedShare,
	ShareholderHolding,
	ShareholderType,
)

__all__ = [
	"ActiveRatioResult", "ChipProfile", "ChipSnapshot", "EffectiveTradableChips",
	"EffectiveTradableChipsResult", "HolderActivity", "RestrictedShare",
	"ShareholderHolding", "ShareholderType",
]
