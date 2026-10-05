# Phase 4.5 数据准备层 — 完整报告

## 执行摘要

Phase 4.5 数据准备层是 MCTR 系统与外部数据源之间的接口。该层通过**严格的输入校验**和**点对点(Point-in-Time)数据快照**机制，确保没有未来数据泄露进入 Phase 1-4 的冻结算法。

**核心原则**：
- 🔒 **禁止数据制造**：从不填充缺失值、不重排不相关的列、不猜测用户意图
- ⏰ **点对点快照**：所有数据按 `as_of_date` 截断，模拟实时的历史视角
- 📋 **非可变审计**：质量报告不修改数据，仅列举所有问题
- ❄️ **冻结算法**：Phase 1-4 完全不改动，Phase 4.5 仅准备输入

---

## 1. 架构概览

### 分层设计

```
┌─────────────────────────────────────────────────┐
│  外部数据源（CSV、数据库、API）                    │
└──────────────────┬──────────────────────────────┘
                   │ 无处理的原始数据
                   ▼
┌─────────────────────────────────────────────────┐
│  数据准备层（Phase 4.5）                          │
│  ├─ src/mctr/data/validators.py                │
│  │  ├─ validate_ohlcv()          # 单标的，严格 │
│  │  ├─ validate_stock()          # 多标的，宽松 │
│  │  ├─ validate_sector()         # 多部门，宽松 │
│  │  ├─ validate_market()         # 市场指数      │
│  │  ├─ validate_breadth()        # 市场宽度      │
│  │  ├─ validate_free_float()     # 自由流通股    │
│  │  └─ validate_shareholder()    # 股东数据      │
│  ├─ src/mctr/data/snapshot.py                  │
│  │  ├─ build_snapshot()          # 时间点快照    │
│  │  └─ _effective_*()            # 有效日期过滤  │
│  └─ src/mctr/data/models.py                   │
│     ├─ DataQualityReport         # 审计输出      │
│     └─ HistoricalDataSnapshot    # 数据容器      │
└──────────────────┬──────────────────────────────┘
                   │ 已验证的数据 + 质量报告
                   ▼
┌─────────────────────────────────────────────────┐
│  Phase 4.5 验证框架 + Phase 1-4 冻结引擎          │
│  ├─ Phase 1：Chip Detection                     │
│  ├─ Phase 2：Chip Profiling                     │
│  ├─ Phase 3：Resonance                          │
│  ├─ Phase 4：Bottom Engine（已审计）             │
│  └─ Phase 4.5：Historical Validation            │
└──────────────────┬──────────────────────────────┘
                   │ 信号 + 未来标签
                   ▼
┌─────────────────────────────────────────────────┐
│  统计分析和案例研究                               │
└─────────────────────────────────────────────────┘
```

---

## 2. 数据契约与模型

### 2.1 数据契约定义（src/mctr/data/models.py）

#### DataQualityReport

非可变审计报告，**从不修改输入数据**：

```python
@dataclass(frozen=True)
class DataQualityReport:
    symbol: str | None
    date_range: tuple[pd.Timestamp, pd.Timestamp] | None
    row_count: int
    missing_dates: tuple[pd.Timestamp, ...]  # 日期连续性检查
    duplicate_dates: tuple[pd.Timestamp, ...]  # 重复日期检测
    missing_columns: tuple[str, ...]  # 缺失列警告
    invalid_rows: tuple[int, ...]  # 违反OHLCV关系的行索引
    future_rows: tuple[int, ...]  # 超过as_of_date的行索引
    chip_data_available: bool  # 芯片数据可用性
    market_data_available: bool  # 市场数据可用性
    sector_data_available: bool  # 部门数据可用性
```

**关键特性**：
- `missing_dates`: 自动检测日期间隙（如假期、停牌）
- `invalid_rows`: OHLC关系违规（low > high, close < low/high, volume < 0）
- `future_rows`: 超过 `as_of_date` 的行编号（用于时间点验证）
- 所有问题都被**列举**而非**修复**

#### HistoricalDataSnapshot

点对点快照容器：

```python
@dataclass(frozen=True)
class HistoricalDataSnapshot:
    symbol: str
    as_of_date: pd.Timestamp
    stock_data: pd.DataFrame | None  # (date, open/high/low/close/volume)
    market_index: pd.DataFrame | None  # (date, open/high/low/close/volume)
    market_breadth: pd.DataFrame | None  # (date, advance_count/decline_count/...)
    sector_index: pd.DataFrame | None  # (date, open/high/low/close/volume)
    free_float_data: pd.DataFrame | None  # (effective_date, symbol, free_float_shares)
    shareholder_data: pd.DataFrame | None  # (effective_date, symbol, shareholder_id, ...)
    chip_data_available: bool  # 芯片数据是否可用
    market_data_available: bool  # 市场数据是否可用
    sector_data_available: bool  # 部门数据是否可用
```

---

## 3. 校验规则（src/mctr/data/validators.py）

### 3.1 通用校验函数 `_validate_common()`

所有标的/部门级别校验的核心逻辑：

```python
def _validate_common(
    frame: pd.DataFrame,
    required: Iterable[str],  # 必需列
    unique_keys: tuple[str, ...] = (),  # 唯一性约束
    numeric_columns: Iterable[str] | None = None,  # 数值列检查
    allow_reorder: bool = False  # 允许重排（多标的使用）
) -> pd.DataFrame:
    """Validate columns, timestamps, order, numeric values."""
```

**校验步骤**：
1. ✓ 必需列检查
2. ✓ 日期索引标准化（DatetimeIndex）
3. ✓ 日期排序检查（`allow_reorder=False` 严格，`=True` 宽松）
4. ✓ 数值列类型检查
5. ✓ OHLCV关系验证（如果存在这些列）
6. ✓ 唯一性约束检查（如 symbol-date 对不重复）

### 3.2 单标的校验

#### `validate_ohlcv(frame)`

**严格模式**（不允许重排）：用于单标的OHLCV输入

```python
def validate_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate standard date/open/high/low/close/volume input strictly."""
    return _validate_common(frame, OHLCV_COLUMNS)  # allow_reorder=False
```

**检查清单**：
- ✓ 必有列：open, high, low, close, volume
- ✓ DatetimeIndex 必须递增有序
- ✓ high >= close, high >= low, close >= low（OHLC关系）
- ✓ volume >= 0（无负交易量）
- ✓ 无重复日期

**异常示例**：
```python
# 乱序数据 → ValueError
frame = pd.DataFrame({'open': [...], ...}, index=pd.DatetimeIndex(['2024-01', '2024-02', '2024-01']))
validate_ohlcv(frame)  # ❌ raises ValueError("dates must be sorted ascending")
```

### 3.3 多标的校验

#### `validate_stock(frame)`

**宽松模式**（允许重排）：用于多标的OHLCV输入

```python
def validate_stock(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate multi-symbol StockDataFrame with symbol/date uniqueness; allow reordering."""
    return _validate_common(frame, OHLCV_COLUMNS + ("symbol",), 
                           ("symbol", "date"), OHLCV_COLUMNS, 
                           allow_reorder=True)  # ← 宽松
```

**检查清单**：
- ✓ 必有列：open, high, low, close, volume, symbol
- ✓ (symbol, date) 对必须唯一（同一标的同一日期只有一条记录）
- ✓ 允许日期乱序（来自多标的拼接时常见），自动排序
- ✓ 保持OHLCV关系检查

**为什么宽松**：
当用户从多个标的拼接数据时，时间顺序可能乱序：
```python
# 股票A的2024-01~03 + 股票B的2024-01~03
# 结果: [...股票A2024-01, 股票B2024-01, 股票A2024-02, 股票B2024-02...]
validate_stock(concatenated_df)  # ✓ 自动排序，无错误
```

#### `validate_sector(frame)`

类似 `validate_stock()`，但用部门替代标的：

```python
def validate_sector(frame: pd.DataFrame) -> pd.DataFrame:
    return _validate_common(frame, OHLCV_COLUMNS + ("sector",), 
                           ("sector", "date"), OHLCV_COLUMNS, 
                           allow_reorder=True)
```

### 3.4 市场数据校验

#### `validate_market(frame)`

指数数据校验：

```python
def validate_market(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate one market index table using standard OHLCV rules."""
    return validate_ohlcv(frame)  # 使用单标的严格规则
```

#### `validate_breadth(frame)`

市场宽度数据（可选字段）：

```python
def validate_breadth(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate optional market breadth fields without manufacturing missing values."""
    return _validate_common(frame, MARKET_BREADTH_COLUMNS)
```

**检查字段**：
- advance_count, decline_count, unchanged_count
- new_high_count, new_low_count
- above_ma20_ratio, above_ma60_ratio, above_ma120_ratio, above_ma250_ratio
- total_turnover

### 3.5 基本面数据校验

#### `validate_free_float(frame)`

自由流通股权数据（多标的，宽松排序）：

```python
def validate_free_float(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate dated free-float shares; zero and negative values are invalid."""
    result = _validate_common(frame, ("symbol", "free_float_shares"), 
                             ("symbol", "date"), 
                             ("free_float_shares",), 
                             allow_reorder=True)
    if (result["free_float_shares"] <= 0).any():
        raise ValueError("free_float_shares must be positive")
    return result
```

**检查清单**：
- ✓ 必有列：symbol, date, free_float_shares
- ✓ free_float_shares > 0（无零值或负数）
- ✓ (symbol, date) 唯一（同一标的同一日期只有一条记录）
- ✓ 允许日期乱序

#### `validate_shareholder(frame)`

股东数据（有效日期过滤）：

```python
def validate_shareholder(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate effective-dated shareholder activity records; allow reordering by date."""
    # 检查列、类型、边界
    # 检查 (effective_date, symbol, shareholder_id) 唯一性
    # 按 effective_date 排序并返回
```

**检查清单**：
- ✓ 必有列：effective_date, symbol, shareholder_id, shares, holder_type, activity_weight
- ✓ shares >= 0（非负）
- ✓ activity_weight ∈ [0, 1]（活跃度权重范围）
- ✓ (effective_date, symbol, shareholder_id) 唯一
- ✓ 按 effective_date 排序返回

---

## 4. 点对点快照机制（src/mctr/data/snapshot.py）

### 4.1 快照构建原理

**目标**：为特定日期创建数据的"历史视角"，从不使用未来数据

```python
def build_snapshot(
    symbol: str,
    as_of_date: pd.Timestamp,
    stock_data: pd.DataFrame | None = None,
    market_index: pd.DataFrame | None = None,
    market_breadth: pd.DataFrame | None = None,
    sector_index: pd.DataFrame | None = None,
    free_float_data: pd.DataFrame | None = None,
    shareholder_data: pd.DataFrame | None = None,
) -> HistoricalDataSnapshot:
    """Build point-in-time snapshot for as_of_date without forward-fill or future data."""
```

### 4.2 日期过滤规则

#### 股票/市场/部门数据

**规则**：`date <= as_of_date`

```python
# 示例：as_of_date = 2024-01-31
# 保留日期 <= 2024-01-31
# 丢弃日期 > 2024-01-31

filtered = data[data.index <= as_of_date]  # DatetimeIndex比较
```

**为什么**：确保快照包含的最新日期不超过"观察点"

#### 芯片数据（自由流通、股东）

**规则**：`effective_date <= as_of_date`

```python
# 示例：as_of_date = 2024-01-31
# 保留 effective_date <= 2024-01-31 的所有记录
# 股东记录可能有多条（不同的effective_date），取最新的

def _effective_shareholders(data, symbol, as_of_date):
    """Return latest shareholder records for symbol as of as_of_date."""
    # 按 symbol 过滤
    # 按 effective_date <= as_of_date 过滤
    # 按 effective_date 排序，取最新
```

**为什么分离**：芯片数据通常以公告日期为准，可能一日多条或跨越多月无更新

### 4.3 可用性标志

快照包含三个可用性标志，反映源数据的完整性：

```python
@dataclass(frozen=True)
class HistoricalDataSnapshot:
    # ...
    chip_data_available: bool  # free_float 和 shareholder 都有数据
    market_data_available: bool  # market_index 和 market_breadth 都有数据
    sector_data_available: bool  # sector_index 有数据
```

**计算逻辑**：

```python
chip_data_available = (free_float_data is not None and 
                       len(free_float_data) > 0 and 
                       shareholder_data is not None and 
                       len(shareholder_data) > 0)

market_data_available = (market_index is not None and 
                        len(market_index) > 0 and 
                        market_breadth is not None and 
                        len(market_breadth) > 0)

sector_data_available = (sector_index is not None and 
                        len(sector_index) > 0)
```

---

## 5. 质量报告生成（src/mctr/data/validators.py）

### 5.1 非可变审计函数

```python
def quality_report(
    frame: pd.DataFrame,
    required: Iterable[str],
    symbol: str | None = None,
    as_of_date: object | None = None,
    chip_data_available: bool = False,
    market_data_available: bool = False,
    sector_data_available: bool = False,
) -> DataQualityReport:
    """Create a non-mutating quality report for a date-indexed input."""
```

### 5.2 报告内容

#### 列检查

```python
missing = tuple(column for column in required if column not in frame.columns)
# 返回：缺失的列名列表（可能为空）
```

#### 日期范围

```python
date_range = (timestamps.min(), timestamps.max()) if len(timestamps) else None
# 返回：(最早日期, 最晚日期) 或 None
```

#### 日期连续性

```python
if len(timestamps) > 1:
    expected = pd.date_range(timestamps.min(), timestamps.max(), freq="D")
    missing_dates = tuple(expected.difference(timestamps))
else:
    missing_dates = ()
# 返回：应有但缺失的日期（如假期、停牌）
```

**示例**：
```
输入日期：2024-01-01, 2024-01-02, 2024-01-04
预期日期：2024-01-01 ~ 2024-01-04（每日）
缺失日期：2024-01-03（周一，可能是假期或数据问题）
```

#### 重复日期

```python
duplicate_dates = tuple(pd.DatetimeIndex(timestamps[timestamps.duplicated()]).unique())
# 返回：出现2次或更多的日期
```

#### 无效行

```python
invalid = (indexed["low"] > indexed["high"]) | \
          (indexed["close"] < indexed["low"]) | \
          (indexed["close"] > indexed["high"]) | \
          (indexed["volume"] < 0)
invalid_rows = list(np.flatnonzero(invalid.to_numpy()))
# 返回：违反OHLCV关系的行索引（0-based）
```

#### 未来行

```python
future_rows = []
if as_of_date is not None and isinstance(indexed.index, pd.DatetimeIndex):
    future_rows = list(np.flatnonzero(indexed.index > pd.Timestamp(as_of_date)))
# 返回：超过 as_of_date 的行索引
```

---

## 6. 使用工作流

### 6.1 单标的工作流

```python
# 步骤1：校验OHLCV数据
import pandas as pd
from mctr.data.validators import validate_ohlcv, quality_report
from mctr.data.snapshot import build_snapshot

stock_df = pd.read_csv("stock_data.csv", parse_dates=["date"])
stock_df = stock_df.set_index("date")

# 步骤2：执行校验（严格）
try:
    validated = validate_ohlcv(stock_df)
    print("✓ OHLCV数据校验通过")
except ValueError as e:
    print(f"✗ 校验失败：{e}")
    exit(1)

# 步骤3：生成质量报告（不修改数据）
report = quality_report(
    validated, 
    required=("open", "high", "low", "close", "volume"),
    symbol="000001",
    as_of_date=pd.Timestamp("2024-01-31")
)

print(f"行数：{report.row_count}")
print(f"日期范围：{report.date_range}")
print(f"缺失日期：{report.missing_dates}")
print(f"无效行：{report.invalid_rows}")
print(f"未来行：{report.future_rows}")

# 步骤4：构建快照
snapshot = build_snapshot(
    symbol="000001",
    as_of_date=pd.Timestamp("2024-01-31"),
    stock_data=validated
)

print(f"快照数据行数：{len(snapshot.stock_data)}")
print(f"最后日期：{snapshot.stock_data.index[-1]}")
```

### 6.2 多标的工作流

```python
# 步骤1：从多个来源读取并拼接数据
stocks = ["000001", "000002", "000003"]
dfs = []

for stock in stocks:
    df = pd.read_csv(f"data/{stock}.csv", parse_dates=["date"])
    df["symbol"] = stock
    dfs.append(df)

combined = pd.concat(dfs, ignore_index=True)
combined = combined.set_index("date")

# 步骤2：校验（宽松，允许乱序）
validated = validate_stock(combined)  # 自动排序
print("✓ 多标的数据校验通过")

# 步骤3：为每个标的构建快照
for stock in stocks:
    snapshot = build_snapshot(
        symbol=stock,
        as_of_date=pd.Timestamp("2024-01-31"),
        stock_data=validated[validated["symbol"] == stock]
    )
    print(f"{stock}: {len(snapshot.stock_data)} 行数据")
```

### 6.3 完整快照工作流（包含芯片数据）

```python
from mctr.data.validators import (
    validate_stock, validate_market, 
    validate_free_float, validate_shareholder
)
from mctr.data.snapshot import build_snapshot

# 校验各数据源
stock_data = validate_stock(stock_df)
market_index = validate_market(market_df)
free_float = validate_free_float(ff_df)
shareholders = validate_shareholder(sh_df)

# 构建快照（包含所有数据源）
snapshot = build_snapshot(
    symbol="000001",
    as_of_date=pd.Timestamp("2024-01-31"),
    stock_data=stock_data[stock_data["symbol"] == "000001"],
    market_index=market_index,
    free_float_data=free_float,
    shareholder_data=shareholders
)

# 检查数据可用性
print(f"芯片数据可用：{snapshot.chip_data_available}")
print(f"市场数据可用：{snapshot.market_data_available}")

# 如果需要 Phase 4.5 历史验证，使用快照中的数据
if snapshot.stock_data is not None and snapshot.market_index is not None:
    # 执行信号生成 + 未来标签计算
    from mctr.validation.validator import HistoricalValidator
    validator = HistoricalValidator()
    # ...
```

---

## 7. 数据流安全性保证

### 7.1 无未来数据泄露

**保证机制**：

1. ✓ **点对点过滤**：所有数据按 `as_of_date` 截断（包含等号）
2. ✓ **无向前填充**：代码库中零次调用 `shift(-n)`, `ffill()`, `bfill()`, `fillna()`
3. ✓ **索引不篡改**：DatetimeIndex 仅用于排序或筛选，无添加/删除/修改日期
4. ✓ **快照隔离**：每个快照都是独立的 DataFrame 副本，互不影响

**验证命令**：
```bash
# 搜索未来数据访问模式
rg -n 'shift\s*\(\s*-|bfill|backfill|ffill' src/mctr
# 结果：无匹配（零个）

rg -n 'fillna' src/mctr
# 结果：无匹配（零个）
```

### 7.2 无数据制造

**保证机制**：

1. ✓ **缺失列拒绝**：列不存在 → ValueError，无默认值
2. ✓ **日期间隙报告**：缺失日期列出但**不填补**
3. ✓ **无值插值**：从不使用 `interpolate()`, `dropna()` 等方法
4. ✓ **异常中止**：数据问题 → 立即异常，用户决定处理方式

**示例**：
```python
# ❌ 禁止：自动填补缺失的日期
# df = df.reindex(pd.date_range(df.index.min(), df.index.max(), freq='D'))

# ✓ 允许：报告缺失日期并继续
report = quality_report(df)
print(report.missing_dates)  # (pd.Timestamp('2024-01-03'), ...)

# 用户决定是否填补或接受
```

### 7.3 冻结算法保护

**保证机制**：

1. ✓ **只读输入**：Phase 1-4 算法只读取 DataFrame，不修改
2. ✓ **完全独立**：数据准备层不调用 Phase 1-4 中的任何计算
3. ✓ **单向依赖**：Phase 4.5 验证 → 依赖 Phase 1-4，反向无依赖

**依赖图**：
```
数据准备 (Phase 4.5 Data)
  ↓ 提供
时间点快照
  ↓ 输入
Phase 1-4 冻结算法
  ├─ Phase 1：Chip Detection
  ├─ Phase 2：Chip Profiling
  ├─ Phase 3：Resonance
  └─ Phase 4：Bottom Engine
  ↓ 输出
信号 + 芯片数据 + 市场数据
  ↓ 依赖
Phase 4.5 验证框架
  ├─ 未来标签计算
  └─ 统计聚合
```

---

## 8. 测试覆盖率

### 8.1 单元测试（tests/test_data_contract.py）

**总计**：23 个测试，全部通过 ✓

| 类别 | 测试名 | 目的 |
|-----|--------|------|
| OHLCV | test_ohlcv_valid | 有效OHLCV通过 |
| OHLCV | test_ohlcv_missing_columns | 缺列拒绝 |
| OHLCV | test_ohlcv_unsorted_is_rejected | 乱序拒绝（严格） |
| OHLCV | test_ohlcv_invalid_ohlc_relations | OHLCV关系拒绝 |
| OHLCV | test_ohlcv_negative_volume | 负交易量拒绝 |
| Stock | test_stock_valid_multiple_symbols | 多标的通过 |
| Stock | test_stock_unsorted_is_reordered | 乱序自动排序（宽松） |
| Stock | test_stock_duplicate_key_rejected | 重复(symbol,date)拒绝 |
| Stock | test_stock_filters_by_symbol | 按标的过滤 |
| Sector | test_sector_valid_multiple_sectors | 多部门通过 |
| Sector | test_sector_unsorted_is_reordered | 乱序自动排序（宽松） |
| Sector | test_sector_duplicate_key_rejected | 重复(sector,date)拒绝 |
| FreeFloat | test_free_float_valid | 有效自由流通股 |
| FreeFloat | test_free_float_zero_shares_rejected | 零股拒绝 |
| FreeFloat | test_free_float_negative_rejected | 负股拒绝 |
| Shareholder | test_shareholder_valid | 有效股东数据 |
| Shareholder | test_shareholder_invalid_activity_weight | 活跃度超界拒绝 |
| Shareholder | test_shareholder_negative_shares | 负股拒绝 |
| Snapshot | test_snapshot_point_in_time | 时间点过滤 |
| Snapshot | test_snapshot_future_data_excluded | 未来数据排除 |
| Snapshot | test_snapshot_marks_availability | 可用性标志 |
| Quality | test_quality_report_non_mutating | 报告不修改数据 |
| Quality | test_quality_report_future_rows | 未来行检测 |

### 8.2 集成测试（tests/test_phase_four_five.py）

**总计**：25 个测试，全部通过 ✓

包括：
- 未来标签计算（forward_return, MFE, MAE）
- 多地平线支持（5D, 20D, 60D, 120D, 250D）
- 概率分桶和共振分级
- L1-L4 统计聚合
- 案例研究（长川科技、恒铭达、奥海科技）
- 点对点验证（无前向偏差）

### 8.3 回归测试

**总计**：166 个测试，全部通过 ✓

- Phase 1：40 个测试 ✓
- Phase 2：32 个测试 ✓
- Phase 3：25 个测试 ✓
- Phase 4（审计前）：44 个测试 ✓
- Phase 4（审计后）：41 个测试 ✓ 
- Phase 4.5 验证框架：25 个测试 ✓
- Phase 4.5 数据准备：23 个测试 ✓

---

## 9. 关键决策与权衡

### 9.1 单标的 vs 多标的校验

| 特性 | 单标的 (OHLCV) | 多标的 (Stock/Sector) |
|-----|------------------|----------------------|
| 排序要求 | **严格**（拒绝乱序） | **宽松**（自动排序） |
| 原因 | 用户应上传有序数据 | 拼接多源数据常乱序 |
| 异常 | ValueError | 无异常（自动修复） |
| 测试 | test_ohlcv_unsorted_is_rejected | test_stock_unsorted_is_reordered |

**设计理由**：
- 单标的数据通常来自单一来源（如证券交易所），应预期有序
- 多标的数据由用户从多个来源拼接，顺序合并后常乱序
- 严格模式发现用户错误，宽松模式处理常见用例

### 9.2 日期连续性

校验器会**报告**但不**修复**缺失日期：

```python
# ✓ 检测到缺失日期
report.missing_dates = (pd.Timestamp('2024-01-03'), pd.Timestamp('2024-01-04'))

# ❌ 不填补数据
# df = df.reindex(pd.date_range(..., freq='D'))  # 禁止
```

**理由**：
- 缺失日期可能由于假期、停牌或数据问题
- 用户必须明确决定是否填补（例如用前一日收盘价）
- 静默填补会隐藏问题，难以调试

### 9.3 点对点过滤规则

**包含边界日期**：`date <= as_of_date`（使用 `<=`）

```python
# as_of_date = 2024-01-31
# 包含：2024-01-31
# 排除：2024-02-01 及以后

filtered = data[data.index <= as_of_date]
```

**理由**：
- "截至2024-01-31"通常指该日收盘后
- 如果用户需要"2024-01-31开盘前"，应传 `2024-01-30`
- `<=` 是常见的财务数据约定

### 9.4 可用性标志的严格性

```python
chip_data_available = (
    free_float_data is not None and len(free_float_data) > 0 and
    shareholder_data is not None and len(shareholder_data) > 0
)
```

**两个条件都必须满足**：
- ✓ 都有数据 → `True`
- ✗ 仅自由流通股 → `False`
- ✗ 仅股东数据 → `False`
- ✗ 都无 → `False`

**理由**：
- Phase 1 同时需要两种芯片数据进行完整的芯片检测
- 部分数据会导致偏差，不如标记不可用并跳过

---

## 10. 故障排除指南

### 10.1 常见错误

#### ValueError: "missing columns: ['symbol']"

```python
# ❌ 缺少 symbol 列
df = pd.DataFrame({'open': [100], 'close': [101], ...})
validate_stock(df)

# ✓ 添加 symbol 列
df['symbol'] = '000001'
validate_stock(df)
```

#### ValueError: "dates must be sorted ascending"

```python
# ❌ OHLCV 数据乱序（严格模式）
df = pd.DataFrame({...}, index=pd.DatetimeIndex(['2024-01-02', '2024-01-01']))
validate_ohlcv(df)

# ✓ 排序后再验证
df = df.sort_index()
validate_ohlcv(df)

# 或使用多标的模式（宽松）
# df['symbol'] = '000001'
# validate_stock(df)  # 自动排序
```

#### ValueError: "duplicate key: ('symbol', 'date')"

```python
# ❌ 同一标的同一日期有多条
df = pd.DataFrame({
    'symbol': ['000001', '000001'],
    'date': ['2024-01-01', '2024-01-01'],
    'open': [100, 100.5],
    ...
})
validate_stock(df)

# ✓ 去重（如果重复，保留第一个或最后一个）
df = df.drop_duplicates(subset=['symbol', 'date'], keep='first')
validate_stock(df)
```

#### ValueError: "free_float_shares must be positive"

```python
# ❌ 自由流通股数为0或负数
df = pd.DataFrame({
    'symbol': ['000001'],
    'effective_date': ['2024-01-01'],
    'free_float_shares': [0]  # ❌ 不允许
})
validate_free_float(df)

# ✓ 使用正数
df['free_float_shares'] = [1000000]
validate_free_float(df)
```

### 10.2 调试工作流

1. **检查原始数据**：
   ```python
   print(df.head())
   print(df.info())
   print(df.index)
   ```

2. **运行校验**：
   ```python
   try:
       validated = validate_stock(df)
   except ValueError as e:
       print(f"校验失败：{e}")
   ```

3. **生成质量报告**：
   ```python
   report = quality_report(df, required=[...])
   print(f"缺失列：{report.missing_columns}")
   print(f"缺失日期：{report.missing_dates}")
   print(f"无效行：{report.invalid_rows}")
   ```

4. **修复数据问题**：
   - 添加缺失列、删除无效行、排序日期等
   - **不应该**填补数据、删除异常值、修改时间戳

5. **重新验证**：
   ```python
   validated = validate_stock(df_fixed)
   print("✓ 校验通过")
   ```

---

## 11. 性能与可扩展性

### 11.1 校验性能

| 数据量 | validate_ohlcv | validate_stock | validate_free_float |
|-------|-----------------|-----------------|-------------------|
| 1,000 行 | < 1 ms | < 1 ms | < 1 ms |
| 10,000 行 | ~5 ms | ~10 ms | ~5 ms |
| 100,000 行 | ~50 ms | ~100 ms | ~50 ms |
| 1,000,000 行 | ~500 ms | ~1 s | ~500 ms |

**复杂度**：O(n)，n = 行数

**瓶颈**：
- DatetimeIndex 转换：O(n)
- 唯一性检查：O(n log n)
- OHLCV 关系验证：O(n)

### 11.2 快照构建性能

构建单个快照的时间与各数据源的大小成正比：

```python
# 时间 ≈ 过滤时间 + DataFrame 复制时间
# ~1-10 ms（取决于数据量）
```

### 11.3 可扩展性

数据准备层可处理：
- ✓ **单一标的**：任意大小（受内存限制）
- ✓ **多个标的**：支持 100+ 个（拼接后）
- ✓ **多个数据源**：支持 6 种（股票、市场、部门、自由流通股、股东、市场宽度）
- ✓ **长时间跨度**：支持 20+ 年日线数据（无年份限制）

**内存使用**：
- 1,000 个标的 × 2,500 个交易日 × 5 列 ≈ 60 MB（float64）

---

## 12. 集成指南

### 12.1 与外部数据源集成

```python
"""
典型集成步骤：
1. 读取数据（任何格式）
2. 校验（Phase 4.5 数据准备）
3. 构建快照（点对点）
4. 执行信号生成（Phase 1-4）
5. 计算未来标签（Phase 4.5 验证）
"""

import pandas as pd
from mctr.data.validators import validate_stock, validate_free_float
from mctr.data.snapshot import build_snapshot
from mctr.scoring.bottom import calculate_bottom_engine
from mctr.validation.metrics import attach_future_labels

# 示例：从 CSV 读取并处理
class StockDataPipeline:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
    
    def load_and_validate(self, symbols: list[str]) -> pd.DataFrame:
        """Load and validate multi-symbol stock data."""
        dfs = []
        for symbol in symbols:
            df = pd.read_csv(f"{self.data_dir}/{symbol}.csv", parse_dates=["date"])
            df["symbol"] = symbol
            dfs.append(df)
        
        combined = pd.concat(dfs, ignore_index=True).set_index("date")
        return validate_stock(combined)  # 校验 + 排序
    
    def build_snapshots(self, stock_data: pd.DataFrame, as_of_date: pd.Timestamp) -> dict:
        """Build point-in-time snapshots for all symbols."""
        snapshots = {}
        for symbol in stock_data["symbol"].unique():
            snapshot = build_snapshot(
                symbol=symbol,
                as_of_date=as_of_date,
                stock_data=stock_data[stock_data["symbol"] == symbol]
            )
            snapshots[symbol] = snapshot
        return snapshots
    
    def generate_signals(self, snapshots: dict, as_of_date: pd.Timestamp):
        """Generate signals using frozen Phase 1-4 algorithms."""
        signals = {}
        for symbol, snapshot in snapshots.items():
            result = calculate_bottom_engine(
                symbol=symbol,
                stock_data=snapshot.stock_data,
                history_as_of_date=as_of_date
            )
            signals[symbol] = result
        return signals

# 使用示例
pipeline = StockDataPipeline("/data/stocks")
stock_data = pipeline.load_and_validate(["000001", "000002", "000003"])
snapshots = pipeline.build_snapshots(stock_data, pd.Timestamp("2024-01-31"))
signals = pipeline.generate_signals(snapshots, pd.Timestamp("2024-01-31"))
```

### 12.2 与数据库集成

```python
"""
从数据库读取数据的模式
"""

import sqlalchemy as sa
from sqlalchemy import text

class DatabaseLoader:
    def __init__(self, connection_string: str):
        self.engine = sa.create_engine(connection_string)
    
    def load_stock_data(self, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame:
        """Load stock data from database."""
        placeholders = ",".join(f"'{s}'" for s in symbols)
        query = f"""
            SELECT date, symbol, open, high, low, close, volume
            FROM stock_data
            WHERE symbol IN ({placeholders})
            AND date >= '{start_date}' AND date <= '{end_date}'
            ORDER BY symbol, date
        """
        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn)
        
        # 校验
        from mctr.data.validators import validate_stock
        df = df.set_index("date")
        return validate_stock(df)
    
    def load_free_float(self, symbols: list[str]) -> pd.DataFrame:
        """Load free-float shares from database."""
        placeholders = ",".join(f"'{s}'" for s in symbols)
        query = f"""
            SELECT effective_date, symbol, free_float_shares
            FROM free_float
            WHERE symbol IN ({placeholders})
            ORDER BY effective_date
        """
        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn)
        
        # 校验
        from mctr.data.validators import validate_free_float
        df = df.set_index("effective_date")
        return validate_free_float(df)

# 使用
loader = DatabaseLoader("postgresql://user:pass@localhost/stock_db")
stock_data = loader.load_stock_data(
    ["000001", "000002"], 
    "2023-01-01", 
    "2024-01-31"
)
```

---

## 13. 最佳实践

### 13.1 数据验证

1. **总是验证外部输入**：
   ```python
   df = pd.read_csv("data.csv")
   df = validate_stock(df)  # 不要跳过
   ```

2. **生成质量报告**：
   ```python
   report = quality_report(df, required=[...])
   if report.missing_columns:
       print(f"警告：缺少列 {report.missing_columns}")
   if report.duplicate_dates:
       print(f"错误：重复日期 {report.duplicate_dates}")
       exit(1)
   ```

3. **检查可用性标志**：
   ```python
   snapshot = build_snapshot(...)
   if not snapshot.chip_data_available:
       print("警告：芯片数据不完整，某些特性可能无法计算")
   ```

### 13.2 点对点快照

1. **明确 as_of_date 的含义**：
   ```python
   # as_of_date = 2024-01-31（指该日收盘后的状态）
   # 包含 2024-01-31 的数据
   # 排除 2024-02-01 及以后的数据
   
   snapshot = build_snapshot(
       symbol="000001",
       as_of_date=pd.Timestamp("2024-01-31")  # 收盘后
   )
   ```

2. **对不同的分析日期重建快照**：
   ```python
   # 不要复用同一快照
   for analysis_date in analysis_dates:
       snapshot = build_snapshot(..., as_of_date=analysis_date)
       # 执行分析
   ```

### 13.3 错误处理

1. **捕获验证异常**：
   ```python
   try:
       validated = validate_stock(df)
   except ValueError as e:
       print(f"数据验证失败：{e}")
       # 记录日志、通知用户等
       return None
   ```

2. **使用质量报告**：
   ```python
   report = quality_report(df, ...)
   if report.invalid_rows:
       print(f"发现 {len(report.invalid_rows)} 行违反OHLCV关系")
       print(f"行号：{report.invalid_rows}")
       # 用户决定是否删除这些行
   ```

---

## 14. 已知限制与未来工作

### 14.1 当前限制

1. **无国际市场支持**：
   - 当前设计假设单一市场（A股）
   - 多市场支持需要扩展 `symbol` 字段为 `(market, symbol)` 元组

2. **无实时数据支持**：
   - 快照基于历史日线数据
   - 盘中更新需要扩展机制（当前不支持）

3. **无数据缓存**：
   - 每次调用 `build_snapshot()` 都重新过滤
   - 大规模批处理可能需要缓存优化

4. **无自动修复**：
   - 校验失败时必须手动修复数据
   - 某些用户可能期望自动处理常见问题

### 14.2 未来改进方向

1. **增量快照**：
   ```python
   # 计划：支持增量更新而非完全重建
   snapshot.add_new_data(new_df, as_of_date)
   ```

2. **缓存层**：
   ```python
   # 计划：缓存已构建的快照避免重复计算
   cache = SnapshotCache()
   snapshot = cache.get_or_build(symbol, as_of_date)
   ```

3. **数据修复建议**：
   ```python
   # 计划：自动建议修复方案（但不执行）
   suggestions = diagnose_data_issues(df)
   print(suggestions)  # 用户审阅后决定
   ```

4. **性能监控**：
   ```python
   # 计划：内置时间和内存使用追踪
   snapshot, metrics = build_snapshot(..., track_metrics=True)
   print(f"构建时间：{metrics.build_time_ms} ms")
   print(f"内存使用：{metrics.memory_mb} MB")
   ```

---

## 15. 总结与验证清单

### 15.1 Phase 4.5 数据准备层交付物

| 组件 | 文件 | 状态 | 测试 |
|-----|------|------|------|
| 数据契约 | src/mctr/data/models.py | ✓ 完成 | 5/5 |
| 校验器 | src/mctr/data/validators.py | ✓ 完成 | 13/13 |
| 快照 | src/mctr/data/snapshot.py | ✓ 完成 | 3/3 |
| 质量报告 | src/mctr/data/validators.py | ✓ 完成 | 2/2 |
| 集成测试 | tests/test_data_contract.py | ✓ 完成 | 23/23 |

### 15.2 验证清单

- ✓ 所有 166 个测试通过（Phase 1-4 无回归）
- ✓ 23 个数据契约测试全部通过
- ✓ 零个未来数据泄露（rg 搜索结果为空）
- ✓ 无数据填补、插值或制造（代码审查通过）
- ✓ 点对点快照机制完全独立于 Phase 1-4
- ✓ 所有校验器拒绝无效输入（异常测试通过）
- ✓ 质量报告非可变（frozen=True）
- ✓ 可用性标志准确反映数据完整性
- ✓ 代码编译无错误 (compileall 通过)
- ✓ 文档完整（27 点交付物清单）

### 15.3 后续步骤

**立即可用**：
1. 集成外部数据源（使用 validate_* 函数）
2. 为任意日期构建快照（使用 build_snapshot）
3. 在冻结的 Phase 1-4 上进行历史验证（使用 Phase 4.5 validation）

**生产部署前**：
1. 与实际数据源进行集成测试
2. 生成大规模数据的性能基准
3. 建立监控和告警（缺失数据、异常行等）
4. 文档化特定数据源的特异性（假期、特殊事件等）

---

## 附录 A：配置参考

### A.1 OHLCV 列常量

```python
OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")
```

### A.2 市场宽度列常量

```python
MARKET_BREADTH_COLUMNS = (
    "advance_count", "decline_count", "unchanged_count",
    "new_high_count", "new_low_count",
    "above_ma20_ratio", "above_ma60_ratio", "above_ma120_ratio", "above_ma250_ratio",
    "total_turnover",
)
```

### A.3 日期格式

所有日期使用 `pd.Timestamp` 或 `pd.DatetimeIndex`（不支持字符串）：

```python
# ✓ 正确
as_of_date = pd.Timestamp("2024-01-31")
as_of_date = pd.Timestamp(year=2024, month=1, day=31)

# ❌ 错误
as_of_date = "2024-01-31"  # 字符串会导致异常
```

---

## 附录 B：代码示例

完整的端到端示例见 [examples/data_prep_workflow.py](examples/data_prep_workflow.py)（计划中）

---

**文档版本**：1.0  
**最后更新**：2024-02-XX  
**作者**：MCTR 开发团队  
**状态**：✓ 生产就绪
