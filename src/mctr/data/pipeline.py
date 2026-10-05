"""Unified data pipeline: load → validate → snapshot."""

from typing import Optional, Union

from datetime import datetime
from pathlib import Path

import pandas as pd

from mctr.data.adapters import DataAdapter, LocalCSVAdapter, LocalParquetAdapter, AdapterConfig
from mctr.data.models import HistoricalDataSnapshot, MarketDataBundle, HistoricalChipInput
from mctr.data.snapshot import build_snapshot
from mctr.data.validators import (
    validate_ohlcv, validate_stock, validate_market, validate_sector,
    validate_free_float, validate_shareholder, validate_breadth,
    quality_report,
)

class DataPipeline:
    """End-to-end data pipeline: raw files → validated snapshots.
    
    Pipeline steps:
    1. Load raw data from adapter (CSV/Parquet)
    2. Validate each data source against contracts
    3. Generate quality reports
    4. Build point-in-time snapshots for specific dates
    5. Expose snapshots to Phase 1-4 algorithms
    """

    def __init__(self, adapter: DataAdapter):
        """Initialize pipeline with a data adapter.
        
        Args:
            adapter: DataAdapter instance (LocalCSVAdapter, LocalParquetAdapter, etc.)
        """
        self.adapter = adapter
        self._raw_data = None
        self._validated_data = None
        self._quality_reports = None

    @classmethod
    def from_csv(cls, data_dir: Union[Path, str] = "data/raw", encoding: str = "utf-8") -> "DataPipeline":
        """Factory: create pipeline from CSV files.
        
        Args:
            data_dir: Directory containing raw CSV files
            encoding: Text encoding for CSV
            
        Returns:
            Initialized DataPipeline
        """
        config = AdapterConfig(data_dir=data_dir, encoding=encoding)
        adapter = LocalCSVAdapter(config)
        return cls(adapter)

    @classmethod
    def from_parquet(cls, data_dir: Union[Path, str] = "data/raw") -> "DataPipeline":
        """Factory: create pipeline from Parquet files.
        
        Args:
            data_dir: Directory containing raw Parquet files
            
        Returns:
            Initialized DataPipeline
        """
        config = AdapterConfig(data_dir=data_dir)
        adapter = LocalParquetAdapter(config)
        return cls(adapter)

    def load(self, validate: bool = True) -> dict:
        """Load and optionally validate all raw data.
        
        Args:
            validate: Whether to validate immediately after loading
            
        Returns:
            Dictionary with keys: 'ohlcv', 'market_index', 'market_breadth',
            'sector_index', 'free_float', 'shareholders'
            
        Raises:
            FileNotFoundError: If required files do not exist
            ValueError: If validation fails and validate=True
        """
        self._raw_data = self.adapter.load_all_data()
        
        if validate:
            self.validate()
        
        return self._raw_data

    def validate(self) -> dict:
        """Validate all loaded data against contracts.
        
        Generates quality reports but never modifies data.
        
        Returns:
            Dictionary with validated DataFrames
            
        Raises:
            ValueError: If data fails validation
        """
        if self._raw_data is None:
            raise RuntimeError("No data loaded. Call load() first.")
        
        validated = {}
        reports = {}
        
        # Validate OHLCV (multi-symbol, allow reordering)
        if self._raw_data["ohlcv"] is not None:
            validated["ohlcv"] = validate_stock(self._raw_data["ohlcv"])
            reports["ohlcv"] = quality_report(
                validated["ohlcv"],
                required=("symbol", "open", "high", "low", "close", "volume")
            )
        
        # Validate market index (single symbol, strict)
        if self._raw_data["market_index"] is not None:
            validated["market_index"] = validate_market(self._raw_data["market_index"])
            reports["market_index"] = quality_report(
                validated["market_index"],
                required=("open", "high", "low", "close", "volume"),
                symbol="MARKET",
                market_data_available=True
            )
        
        # Validate market breadth (optional)
        if self._raw_data["market_breadth"] is not None:
            try:
                validated["market_breadth"] = validate_breadth(self._raw_data["market_breadth"])
                reports["market_breadth"] = quality_report(
                    validated["market_breadth"],
                    required=("advance_count", "decline_count", "unchanged_count"),
                    symbol="MARKET_BREADTH"
                )
            except ValueError as e:
                print(f"⚠️ Market breadth validation failed: {e}")
                validated["market_breadth"] = None
        
        # Validate sector indices (multi-sector, allow reordering)
        if self._raw_data["sector_index"] is not None:
            validated["sector_index"] = validate_sector(self._raw_data["sector_index"])
            reports["sector_index"] = quality_report(
                validated["sector_index"],
                required=("sector", "open", "high", "low", "close", "volume"),
                symbol="SECTOR"
            )
        
        # Validate free-float (optional, multi-symbol, allow reordering)
        if self._raw_data["free_float"] is not None:
            try:
                validated["free_float"] = validate_free_float(self._raw_data["free_float"])
                reports["free_float"] = quality_report(
                    validated["free_float"],
                    required=("symbol", "free_float_shares"),
                    symbol="FREE_FLOAT",
                    chip_data_available=True
                )
            except ValueError as e:
                print(f"⚠️ Free-float validation failed: {e}")
                validated["free_float"] = None
        
        # Validate shareholders (optional)
        if self._raw_data["shareholders"] is not None:
            try:
                validated["shareholders"] = validate_shareholder(self._raw_data["shareholders"])
                reports["shareholders"] = quality_report(
                    validated["shareholders"],
                    required=("symbol", "shareholder_id", "shares", "activity_weight"),
                    symbol="SHAREHOLDERS",
                    chip_data_available=True
                )
            except ValueError as e:
                print(f"⚠️ Shareholder validation failed: {e}")
                validated["shareholders"] = None
        
        self._validated_data = validated
        self._quality_reports = reports
        
        return validated

    def get_quality_reports(self) -> dict:
        """Get quality reports for all data sources.
        
        Returns:
            Dictionary of DataQualityReport objects keyed by source name
        """
        if self._quality_reports is None:
            raise RuntimeError("No validation performed. Call validate() first.")
        return self._quality_reports

    def print_quality_summary(self) -> None:
        """Print human-readable quality summary."""
        if self._quality_reports is None:
            print("No validation performed. Call validate() first.")
            return
        
        print("\n" + "=" * 80)
        print("DATA QUALITY SUMMARY")
        print("=" * 80)
        
        for name, report in self._quality_reports.items():
            print(f"\n📊 {name.upper()}")
            print(f"   Rows: {report.row_count}")
            print(f"   Date range: {report.date_range}")
            if report.missing_columns:
                print(f"   ❌ Missing columns: {report.missing_columns}")
            if report.invalid_rows:
                print(f"   ❌ Invalid rows: {len(report.invalid_rows)}")
            if report.duplicate_dates:
                print(f"   ❌ Duplicate dates: {len(report.duplicate_dates)}")
            if report.missing_dates:
                print(f"   ⚠️  Missing dates: {len(report.missing_dates)} (gaps/holidays)")
            if report.future_rows:
                print(f"   ⚠️  Future rows: {len(report.future_rows)} (will be filtered)")
            else:
                print(f"   ✓ All checks passed")

    def build_snapshot(
        self,
        symbol: str,
        as_of_date: Union[Union[datetime, pd.Timestamp], str],
    ) -> HistoricalDataSnapshot:
        """Build point-in-time snapshot for one symbol at one date.
        
        Args:
            symbol: Stock code (e.g., "000001")
            as_of_date: Observation date (date <= as_of_date only)
            
        Returns:
            HistoricalDataSnapshot with all data filtered by as_of_date
            
        Raises:
            RuntimeError: If data not loaded and validated
            ValueError: If symbol not found
        """
        if self._validated_data is None:
            raise RuntimeError("No validated data. Call load() and validate() first.")
        
        # Normalize as_of_date
        if isinstance(as_of_date, str):
            as_of_date = pd.Timestamp(as_of_date)
        elif isinstance(as_of_date, datetime):
            as_of_date = pd.Timestamp(as_of_date)
        
        # Extract stock data for this symbol
        stock_data = None
        if self._validated_data.get("ohlcv") is not None:
            stock_df = self._validated_data["ohlcv"]
            stock_symbol_data = stock_df[stock_df["symbol"] == symbol]
            if not stock_symbol_data.empty:
                stock_data = stock_symbol_data.copy()
        
        if stock_data is None:
            raise ValueError(f"Symbol {symbol} not found in OHLCV data")
        
        # Extract market data
        market_data = None
        if self._validated_data.get("market_index") is not None:
            market_df = self._validated_data["market_index"]
            market_breadth_df = self._validated_data.get("market_breadth")
            market_data = MarketDataBundle(
                indices={"market": market_df},
                breadth=market_breadth_df
            )
        
        # Extract sector data
        sector_data = None
        if self._validated_data.get("sector_index") is not None:
            sector_data = self._validated_data["sector_index"]
        
        # Extract chip data (free-float + shareholders)
        free_float_data = None
        shareholder_data = None
        if self._validated_data.get("free_float") is not None:
            ff_df = self._validated_data["free_float"]
            free_float_symbol = ff_df[ff_df["symbol"] == symbol]
            if not free_float_symbol.empty:
                free_float_data = free_float_symbol.copy()
        
        if self._validated_data.get("shareholders") is not None:
            sh_df = self._validated_data["shareholders"]
            shareholders_symbol = sh_df[sh_df["symbol"] == symbol]
            if not shareholders_symbol.empty:
                shareholder_data = shareholders_symbol.copy()
        
        chip_input = HistoricalChipInput(
            free_float=free_float_data,
            shareholders=shareholder_data,
            chip_data_available=(free_float_data is not None and shareholder_data is not None)
        )
        
        # Use the existing snapshot builder
        snapshot = build_snapshot(
            as_of_date=as_of_date,
            symbol=symbol,
            stock_ohlcv=stock_data,
            market_data=market_data,
            sector_data=sector_data,
            free_float=free_float_data,
            shareholders=shareholder_data,
        )
        
        return snapshot

    def build_snapshots_for_date(
        self,
        as_of_date: Union[Union[datetime, pd.Timestamp], str],
        symbols: Optional[list[str]] = None,
    ) -> dict[str, HistoricalDataSnapshot]:
        """Build snapshots for multiple symbols at the same date.
        
        Args:
            as_of_date: Observation date
            symbols: List of symbols to process. If None, use all symbols in OHLCV.
            
        Returns:
            Dictionary of {symbol: HistoricalDataSnapshot}
        """
        if self._validated_data is None:
            raise RuntimeError("No validated data. Call load() and validate() first.")
        
        if symbols is None:
            if self._validated_data.get("ohlcv") is None:
                raise ValueError("No OHLCV data to extract symbols from")
            symbols = self._validated_data["ohlcv"]["symbol"].unique().tolist()
        
        snapshots = {}
        for symbol in symbols:
            try:
                snapshot = self.build_snapshot(symbol, as_of_date)
                snapshots[symbol] = snapshot
            except ValueError as e:
                print(f"⚠️ Failed to build snapshot for {symbol}: {e}")
        
        return snapshots
