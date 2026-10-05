"""Base adapter interface for historical data loading."""

from typing import Optional, Union

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

@dataclass
class AdapterConfig:
    """Configuration for data adapters."""

    data_dir: Union[Path, str] = "data/raw"
    """Root directory containing raw data files."""

    encoding: str = "utf-8"
    """Text encoding for CSV files."""

    date_format: Optional[str] = "%Y-%m-%d"
    """Date format string for parsing."""

    parse_dates: bool = True
    """Whether to parse date columns automatically."""

    validate_on_load: bool = True
    """Whether to validate data immediately after loading."""

    allow_future_data: bool = False
    """Whether to allow data beyond as_of_date (should be False for PIT)."""

class DataAdapter(ABC):
    """Abstract base adapter for loading and validating raw data.
    
    All adapters:
    - Load data from a source (CSV, Parquet, database)
    - Apply minimal transformations (index creation, type coercion)
    - Return DataFrame with strict schema enforcement
    - Never fabricate, fill, or impute missing data
    - Support point-in-time filtering (date <= as_of_date)
    """

    def __init__(self, config: AdapterConfig = AdapterConfig()):
        """Initialize adapter with configuration.
        
        Args:
            config: AdapterConfig with paths and parsing options
        """
        self.config = config
        self.data_dir = Path(config.data_dir)

    @abstractmethod
    def load_ohlcv(self) -> pd.DataFrame:
        """Load multi-symbol OHLCV data.
        
        Returns:
            DataFrame with DatetimeIndex, columns: symbol, open, high, low, close, volume
            
        Raises:
            FileNotFoundError: If file does not exist
            ValueError: If data format is invalid
        """
        pass

    @abstractmethod
    def load_market_index(self) -> pd.DataFrame:
        """Load market index OHLCV.
        
        Returns:
            DataFrame with DatetimeIndex, columns: open, high, low, close, volume
        """
        pass

    @abstractmethod
    def load_market_breadth(self) -> Optional[pd.DataFrame]:
        """Load optional market breadth data.
        
        Returns:
            DataFrame with breadth columns, or None if not available
        """
        pass

    @abstractmethod
    def load_sector_index(self) -> pd.DataFrame:
        """Load sector indices OHLCV.
        
        Returns:
            DataFrame with DatetimeIndex, columns: sector, open, high, low, close, volume
        """
        pass

    @abstractmethod
    def load_free_float(self) -> Optional[pd.DataFrame]:
        """Load free-float shares data.
        
        Returns:
            DataFrame with effective_date index, columns: symbol, free_float_shares
            or None if not available
        """
        pass

    @abstractmethod
    def load_shareholders(self) -> Optional[pd.DataFrame]:
        """Load shareholder activity data.
        
        Returns:
            DataFrame with effective_date index, columns: symbol, shareholder_id, 
            shares, holder_type, activity_weight
            or None if not available
        """
        pass

    def load_all_data(self) -> dict:
        """Convenience method to load all data sources at once.
        
        Returns:
            Dictionary with keys: 'ohlcv', 'market_index', 'market_breadth',
            'sector_index', 'free_float', 'shareholders'
        """
        return {
            "ohlcv": self.load_ohlcv(),
            "market_index": self.load_market_index(),
            "market_breadth": self.load_market_breadth(),
            "sector_index": self.load_sector_index(),
            "free_float": self.load_free_float(),
            "shareholders": self.load_shareholders(),
        }

    def _ensure_date_index(self, df: pd.DataFrame, date_column: str = "date") -> pd.DataFrame:
        """Ensure DataFrame has DatetimeIndex.
        
        Args:
            df: Input DataFrame
            date_column: Column name containing dates (if not already indexed)
            
        Returns:
            DataFrame with DatetimeIndex
            
        Raises:
            ValueError: If no date column found
        """
        if isinstance(df.index, pd.DatetimeIndex):
            return df
        if date_column in df.columns:
            df = df.copy()
            df[date_column] = pd.to_datetime(df[date_column], format=self.config.date_format)
            df = df.set_index(date_column)
            return df
        raise ValueError(f"No date column '{date_column}' found and index is not DatetimeIndex")

    def _apply_pit_filter(self, df: pd.DataFrame, as_of_date: pd.Timestamp) -> pd.DataFrame:
        """Filter DataFrame to point-in-time (date <= as_of_date).
        
        Args:
            df: DataFrame with DatetimeIndex
            as_of_date: Cutoff date
            
        Returns:
            Filtered DataFrame containing only date <= as_of_date
        """
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame must have DatetimeIndex for PIT filtering")
        return df[df.index <= as_of_date]
