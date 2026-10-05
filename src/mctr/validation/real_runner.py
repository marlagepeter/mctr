"""Runner for executing MCTR Phases 1-4 on real historical data."""

from typing import Optional

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from mctr.config import BottomConfig, ChipConfig
from mctr.data.models import HistoricalDataSnapshot
from mctr.data.pipeline import DataPipeline
from mctr.resonance import calculate_resonance, build_stock_regime
from mctr.scoring.bottom import calculate_bottom_engine
from mctr.sector import calculate_sector_regime
from mctr.market import calculate_market_regime
from mctr.position import calculate_position_percentiles
from mctr.momentum import calculate_momentum_features
from mctr.trend import calculate_trend_state
from mctr.indicators import calculate_exhaustion_features
from mctr.chips import effective_free_float, calculate_active_ratio

@dataclass(frozen=True)
class RealRunResult:
    """Point-in-time signal from running all phases."""

    symbol: str
    as_of_date: pd.Timestamp
    
    # Phase 1-4 outputs
    position_score: Optional[float] = None
    momentum_score: Optional[float] = None
    trend_state: Optional[str] = None
    exhaustion_score: Optional[float] = None
    chip_score: Optional[float] = None
    
    # Phase 3 outputs
    market_regime: Optional[str] = None
    market_strength: Optional[float] = None
    sector_regime: Optional[str] = None
    sector_strength: Optional[float] = None
    resonance_strength: Optional[float] = None
    
    # Phase 4 outputs
    bottom_probability: Optional[float] = None
    bottom_level: Optional[str] = None
    risk_state: Optional[str] = None
    confidence: Optional[str] = None
    
    # Data availability
    chip_data_available: bool = False
    market_data_available: bool = False
    sector_data_available: bool = False

class RealRunner:
    """Execute Phase 1-4 on real historical data.
    
    This runner:
    - Loads data via DataPipeline
    - Builds point-in-time snapshots
    - Runs Phase 1-4 algorithms
    - Collects signals with data availability flags
    - Prepares output for validation framework
    """

    def __init__(
        self,
        pipeline: DataPipeline,
        chip_config: ChipConfig = ChipConfig(),
        bottom_config: BottomConfig = BottomConfig(),
    ):
        """Initialize runner with data pipeline and configs.
        
        Args:
            pipeline: Initialized DataPipeline (loaded and validated)
            chip_config: Chip profiling configuration
            bottom_config: Bottom Engine configuration
        """
        self.pipeline = pipeline
        self.chip_config = chip_config
        self.bottom_config = bottom_config

    def run_symbol_date(self, symbol: str, as_of_date: pd.Timestamp) -> Optional[RealRunResult]:
        """Run Phase 1-4 for one symbol at one date.
        
        Args:
            symbol: Stock code
            as_of_date: Observation date (point-in-time)
            
        Returns:
            RealRunResult with all Phase 1-4 outputs, or None if execution fails
        """
        try:
            # Build point-in-time snapshot
            snapshot = self.pipeline.build_snapshot(symbol, as_of_date)
            
            # Extract OHLCV
            if snapshot.stock_ohlcv is None or snapshot.stock_ohlcv.empty:
                return None
            
            stock_data = snapshot.stock_ohlcv
            current_price = stock_data.iloc[-1]["close"]
            market_data = snapshot.market_data
            
            # Phase 1: Position percentiles
            position_percentiles = calculate_position_percentiles(
                stock_data,
                config=self.bottom_config
            )
            position_score = float(position_percentiles.get(60, 0.5))
            
            # Phase 1: Momentum features
            momentum_features = calculate_momentum_features(stock_data)
            momentum_score = float(list(momentum_features.values())[0]) if momentum_features else 0.5
            
            # Phase 1: Trend state
            trend_state = calculate_trend_state(stock_data, config=self.bottom_config) or "T3"
            
            # Phase 1: Exhaustion features
            exhaustion_features = calculate_exhaustion_features(
                stock_data,
                config=self.bottom_config
            )
            exhaustion_score = float(list(exhaustion_features.values())[0]) if exhaustion_features else 0.5
            
            # Phase 2: Chip profile
            chip_profile = None
            chip_score = 0.5
            
            if snapshot.free_float is not None and not snapshot.free_float.empty:
                try:
                    # Get latest free-float
                    ff_row = snapshot.free_float.iloc[-1]
                    free_float = float(ff_row["free_float_shares"])
                    
                    # Get shareholdings
                    holdings = None
                    if snapshot.shareholders is not None and not snapshot.shareholders.empty:
                        holdings = [
                            {
                                "shareholder_id": row["shareholder_id"],
                                "shares": row["shares"],
                                "shareholder_type": row["holder_type"],
                                "activity_weight": row["activity_weight"],
                            }
                            for _, row in snapshot.shareholders.iterrows()
                        ]
                    
                    # Calculate active ratio
                    active_ratio = calculate_active_ratio(
                        free_float=free_float,
                        holdings=holdings,
                        config=self.chip_config,
                        as_of_date=as_of_date
                    )
                    
                    # Simplified chip score
                    chip_score = float(active_ratio.active_ratio)
                except Exception as e:
                    print(f"Warning: Failed to calculate chip score: {e}")
            
            # Phase 3: Market regime
            market_regime = "M3"
            market_strength = 0.5
            market_gate = 1.0
            if market_data and market_data.indices.get("market") is not None:
                try:
                    market_result = calculate_market_regime(
                        market_data.indices["market"],
                        config=self.bottom_config
                    )
                    market_regime = getattr(market_result, "regime", "M3")
                    market_strength = float(getattr(market_result, "market_strength", 0.5))
                    market_gate = float(getattr(market_result, "market_gate", 1.0))
                except Exception as e:
                    print(f"Warning: Failed to calculate market regime: {e}")
            
            # Phase 3: Sector regime
            sector_regime = "S3"
            sector_strength = 0.5
            relative_strength = 0.5
            if snapshot.sector_data is not None and not snapshot.sector_data.empty:
                try:
                    sector_result = calculate_sector_regime(
                        snapshot.sector_data,
                        config=self.bottom_config
                    )
                    sector_regime = getattr(sector_result, "regime", "S3")
                    sector_strength = float(getattr(sector_result, "sector_strength", 0.5))
                    relative_strength = float(getattr(sector_result, "relative_strength", 0.5))
                except Exception as e:
                    print(f"Warning: Failed to calculate sector regime: {e}")
            
            # Phase 3: Resonance
            resonance_strength = 0.5
            try:
                stock_regime = build_stock_regime(
                    position_score,
                    momentum_score,
                    exhaustion_score,
                    chip_score
                )
                resonance = calculate_resonance(
                    market_regime=market_regime,
                    sector_regime=sector_regime,
                    stock_regime=stock_regime,
                )
                resonance_strength = float(
                    getattr(resonance, "resonance_strength", 0.5)
                )
            except Exception as e:
                print(f"Warning: Failed to calculate resonance: {e}")
            
            # Phase 4: Bottom Engine
            bottom_probability = 0.5
            bottom_level = "NONE"
            risk_state = "R0"
            confidence = "low"
            
            try:
                bottom_result = calculate_bottom_engine(
                    as_of_date=as_of_date,
                    position_percentiles=position_percentiles,
                    chip_profile=chip_profile,  # Simplified, would need full chip profile
                    exhaustion_features=exhaustion_features,
                    momentum_features=momentum_features,
                    trend_state=trend_state,
                    resonance=resonance_strength if isinstance(resonance_strength, (int, float)) else 0.5,
                    current_price=current_price,
                    history=stock_data,
                    market_state=market_regime,
                    sector_relative_strength=relative_strength,
                    config=self.bottom_config,
                    history_as_of_date=as_of_date,
                )
                bottom_probability = float(bottom_result.bottom_probability)
                bottom_level = str(bottom_result.bottom_level)
                risk_state = str(bottom_result.risk_state)
                confidence = str(bottom_result.confidence)
            except Exception as e:
                print(f"Warning: Failed to calculate bottom engine: {e}")
            
            return RealRunResult(
                symbol=symbol,
                as_of_date=as_of_date,
                position_score=position_score,
                momentum_score=momentum_score,
                trend_state=trend_state,
                exhaustion_score=exhaustion_score,
                chip_score=chip_score,
                market_regime=market_regime,
                market_strength=market_strength,
                sector_regime=sector_regime,
                sector_strength=sector_strength,
                resonance_strength=resonance_strength,
                bottom_probability=bottom_probability,
                bottom_level=bottom_level,
                risk_state=risk_state,
                confidence=confidence,
                chip_data_available=snapshot.chip_data_available,
                market_data_available=snapshot.market_data_available,
                sector_data_available=snapshot.sector_data_available,
            )
        
        except Exception as e:
            print(f"Error running {symbol} at {as_of_date}: {e}")
            return None

    def run_dates(
        self,
        dates: list[pd.Timestamp],
        symbols: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """Run Phase 1-4 for multiple dates and symbols.
        
        Args:
            dates: List of observation dates
            symbols: List of symbols. If None, use all from OHLCV.
            
        Returns:
            DataFrame with one row per (symbol, date) result
        """
        if symbols is None:
            if self.pipeline._validated_data is None:
                raise RuntimeError("Pipeline data not loaded. Call pipeline.load() first.")
            ohlcv = self.pipeline._validated_data.get("ohlcv")
            if ohlcv is None:
                raise ValueError("No OHLCV data found")
            symbols = ohlcv["symbol"].unique().tolist()
        
        results = []
        total = len(dates) * len(symbols)
        count = 0
        
        for as_of_date in dates:
            for symbol in symbols:
                result = self.run_symbol_date(symbol, as_of_date)
                if result:
                    results.append(result)
                count += 1
                if count % max(1, total // 10) == 0:
                    print(f"Progress: {count}/{total} ({100*count//total}%)")
        
        # Convert results to DataFrame
        df = pd.DataFrame([
            {
                "symbol": r.symbol,
                "date": r.as_of_date,
                "position_score": r.position_score,
                "momentum_score": r.momentum_score,
                "trend_state": r.trend_state,
                "exhaustion_score": r.exhaustion_score,
                "chip_score": r.chip_score,
                "market_regime": r.market_regime,
                "market_strength": r.market_strength,
                "sector_regime": r.sector_regime,
                "sector_strength": r.sector_strength,
                "resonance_strength": r.resonance_strength,
                "bottom_probability": r.bottom_probability,
                "bottom_level": r.bottom_level,
                "risk_state": r.risk_state,
                "confidence": r.confidence,
                "chip_data_available": r.chip_data_available,
                "market_data_available": r.market_data_available,
                "sector_data_available": r.sector_data_available,
            }
            for r in results
        ])
        
        return df
