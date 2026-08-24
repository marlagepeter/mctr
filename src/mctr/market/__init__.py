"""Market regime extension point."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketRegimeInputs:
    """Contract for index, breadth, liquidity, and market indicator inputs."""

    index_name: str
    breadth: float | None = None
    new_highs: int | None = None
    new_lows: int | None = None
    above_ma_20: float | None = None
    above_ma_60: float | None = None
    above_ma_120: float | None = None
    above_ma_250: float | None = None
    turnover: float | None = None


# TODO: implement independent regime calculations for required A-share indices.
