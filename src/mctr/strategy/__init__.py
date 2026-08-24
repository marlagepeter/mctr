"""MCTR strategy state-machine extension point."""

from enum import IntEnum


class StrategyState(IntEnum):
    S0_WAITING = 0
    S1_LOW_OBSERVATION = 1
    S2_STRATEGIC_ENTRY = 2
    S3_TREND_HOLDING = 3
    S4_HIGH_ALERT = 4
    S5_STRATEGIC_EXIT = 5


# TODO: implement transitions after Bottom/Top/Risk engines are calibrated.
