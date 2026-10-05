"""Local Parquet adapter for loading raw historical data."""

from typing import Optional

from pathlib import Path

import pandas as pd

from .base import DataAdapter, AdapterConfig

class LocalParquetAdapter(DataAdapter):
    """Load raw data from local Parquet files.
    
    Expected directory structure:
        data/raw/
        ├── ohlcv/
        │   └── stocks_ohlcv.parquet
        ├── market/
        │   ├── market_index.parquet
        │   └── market_breadth.parquet (optional)
        ├── sector/
        │   └── sector_index.parquet
        ├── fundamental/
        │   ├── free_float.parquet (optional)
        │   └── shareholders.parquet (optional)
    """

    def __init__(self, config: AdapterConfig = AdapterConfig()):
        """Initialize Parquet adapter.
        
        Args:
            config: AdapterConfig with data_dir and parsing options
        """
        super().__init__(config)
        self._validate_data_dir()

    def _validate_data_dir(self) -> None:
        """Ensure data directory exists."""
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")

    def _load_parquet(self, relative_path: str) -> pd.DataFrame:
        """Load a Parquet file.
        
        Args:
            relative_path: Path relative to data_dir (e.g., "ohlcv/stocks_ohlcv.parquet")
            
        Returns:
            Loaded DataFrame
            
        Raises:
            FileNotFoundError: If file does not exist
        """
        file_path = self.data_dir / relative_path
        if not file_path.exists():
            raise FileNotFoundError(f"Parquet file not found: {file_path}")
        
        return pd.read_parquet(file_path)

    def load_ohlcv(self) -> pd.DataFrame:
        """Load multi-symbol OHLCV data.
        
        Expected columns: date, symbol, open, high, low, close, volume
        
        Returns:
            DataFrame with DatetimeIndex (date), columns: symbol, open, high, low, close, volume
        """
        df = self._load_parquet("ohlcv/stocks_ohlcv.parquet")
        df = self._ensure_date_index(df, "date")
        
        # Ensure symbol column exists
        if "symbol" not in df.columns:
            raise ValueError("OHLCV must include 'symbol' column")
        
        return df

    def load_market_index(self) -> pd.DataFrame:
        """Load market index OHLCV.
        
        Expected columns: date, open, high, low, close, volume
        
        Returns:
            DataFrame with DatetimeIndex (date), columns: open, high, low, close, volume
        """
        df = self._load_parquet("market/market_index.parquet")
        df = self._ensure_date_index(df, "date")
        return df

    def load_market_breadth(self) -> Optional[pd.DataFrame]:
        """Load optional market breadth data.
        
        Expected columns: date, advance_count, decline_count, etc.
        
        Returns:
            DataFrame or None if file does not exist
        """
        try:
            df = self._load_parquet("market/market_breadth.parquet")
            df = self._ensure_date_index(df, "date")
            return df
        except FileNotFoundError:
            return None

    def load_sector_index(self) -> pd.DataFrame:
        """Load sector indices OHLCV.
        
        Expected columns: date, sector, open, high, low, close, volume
        
        Returns:
            DataFrame with DatetimeIndex (date), columns: sector, open, high, low, close, volume
        """
        df = self._load_parquet("sector/sector_index.parquet")
        df = self._ensure_date_index(df, "date")
        
        # Ensure sector column exists
        if "sector" not in df.columns:
            raise ValueError("Sector index must include 'sector' column")
        
        return df

    def load_free_float(self) -> Optional[pd.DataFrame]:
        """Load free-float shares data.
        
        Expected columns: effective_date, symbol, free_float_shares
        
        Returns:
            DataFrame or None if file does not exist
        """
        try:
            df = self._load_parquet("fundamental/free_float.parquet")
            df = self._ensure_date_index(df, "effective_date")
            return df
        except FileNotFoundError:
            return None

    def load_shareholders(self) -> Optional[pd.DataFrame]:
        """Load shareholder activity data.
        
        Expected columns: effective_date, symbol, shareholder_id, shares, holder_type, activity_weight
        
        Returns:
            DataFrame or None if file does not exist
        """
        try:
            df = self._load_parquet("fundamental/shareholders.parquet")
            df = self._ensure_date_index(df, "effective_date")
            return df
        except FileNotFoundError:
            return None
