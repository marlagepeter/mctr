"""Data adapters for loading raw historical data from various sources."""

from .base import DataAdapter, AdapterConfig
from .local_csv import LocalCSVAdapter
from .local_parquet import LocalParquetAdapter

__all__ = [
    "DataAdapter",
    "AdapterConfig",
    "LocalCSVAdapter",
    "LocalParquetAdapter",
]
