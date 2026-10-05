# MCTR 真实数据需求规范

## 文档目的

本文档定义 MCTR 系统接入真实 A 股历史数据所需的**数据合约**和**格式要求**。这是步骤 1（数据层审计）和步骤 2（数据适配器）的基础。

**重要原则**：
- 🔒 严格定义必需字段、类型、范围
- 📋 明确指出哪些字段可缺失（打标记）、哪些必须拒绝
- ⏰ Point-in-time 要求绝对执行
- 🚫 不制造、填补、猜测任何数据

---

## 1. 数据源概览

### 1.1 必需数据源

| 数据源 | 类型 | 用途 | 优先级 | 缺失处理 |
|-------|------|------|--------|---------|
| **股票 OHLCV** | CSV/Parquet | Phase 1-4 核心输入 | ⭐⭐⭐ (必需) | 拒绝运行 |
| **市场指数** | CSV/Parquet | Market Regime (Phase 3) | ⭐⭐⭐ (必需) | 拒绝运行 |
| **行业指数** | CSV/Parquet | Sector Regime (Phase 3) | ⭐⭐⭐ (必需) | 拒绝运行 |
| **自由流通股** | CSV/Parquet | Chip Profile (Phase 2) | ⭐⭐ (重要) | 标记不完整，继续运行 |
| **股东数据** | CSV/Parquet | Chip Profile (Phase 2) | ⭐⭐ (重要) | 标记不完整，继续运行 |
| **市场宽度** | CSV/Parquet | Market Regime 增强 (Phase 3) | ⭐ (可选) | 跳过，不影响 |

### 1.2 数据文件结构

```
data/raw/
├── ohlcv/
│   ├── stocks_ohlcv.csv        # 多标的 OHLCV (必需)
│   └── stocks_ohlcv.parquet    # 或 Parquet 格式
├── market/
│   ├── market_index.csv        # 市场指数 (必需)
│   ├── market_breadth.csv      # 市场宽度 (可选)
│   └── market_*.parquet
├── sector/
│   ├── sector_index.csv        # 行业指数 (必需)
│   └── sector_*.parquet
├── fundamental/
│   ├── free_float.csv          # 自由流通股 (重要)
│   ├── shareholders.csv        # 股东数据 (重要)
│   └── *.parquet
└── README.md                    # 数据源说明
```

---

## 2. OHLCV 数据（股票价格）

### 2.1 必需字段

| 字段名 | 类型 | 格式 | 约束 | 说明 |
|-------|------|------|------|------|
| `date` | DateTime | YYYY-MM-DD | 工作日，唯一 | 交易日期 |
| `symbol` | String | "000001" (6位数字) | A股代码，唯一 | 股票代码 |
| `open` | Float | 0.01～10000 | > 0 | 开盘价（复权） |
| `high` | Float | 0.01～10000 | >= close, >= low | 最高价（复权） |
| `low` | Float | 0.01～10000 | <= close, <= high | 最低价（复权） |
| `close` | Float | 0.01～10000 | > 0 | 收盘价（复权） |
| `volume` | Float/Int | 0～1e10 | >= 0 | 成交股数（原始数值） |

### 2.2 数据质量要求

**OHLC 关系验证**：
```
high >= close >= low
high >= low
```

**成交量检查**：
- volume >= 0（无负数）
- volume == 0 可接受（停牌等情况）

**日期要求**：
- DatetimeIndex 按升序排列
- 无重复日期（单标的）
- 日期范围：至少 2,500 个交易日（~10 年）

**复权要求**：
- 所有 OHLCV 必须是**前复权后的价格**
- 不能混合复权和非复权数据
- 建议在数据导入前由数据源处理复权

### 2.3 CSV 格式示例

```csv
date,symbol,open,high,low,close,volume
2023-01-02,000001,10.50,10.65,10.40,10.60,5000000
2023-01-03,000001,10.60,10.80,10.55,10.75,4800000
2023-01-04,000001,10.75,10.90,10.60,10.80,5200000
...
```

### 2.4 Parquet 架构

```python
# 推荐 Parquet schema
{
    "date": "timestamp[ns]",
    "symbol": "string",
    "open": "float64",
    "high": "float64",
    "low": "float64",
    "close": "float64",
    "volume": "int64"  # 或 float64
}
```

### 2.5 验证规则

```python
# 校验器调用
from mctr.data.validators import validate_stock, quality_report

df = pd.read_csv("stocks_ohlcv.csv", parse_dates=["date"])
df = df.set_index("date")

# 校验（自动排序多标的）
try:
    validated = validate_stock(df)
except ValueError as e:
    print(f"❌ 校验失败：{e}")
    exit(1)

# 质量报告（不修改数据）
report = quality_report(validated, required=("open", "high", "low", "close", "volume"))
if report.missing_dates:
    print(f"⚠️ 缺失日期：{report.missing_dates}")
if report.invalid_rows:
    print(f"❌ 无效行：{report.invalid_rows}")
```

---

## 3. 市场指数数据

### 3.1 市场指数（必需）

| 字段名 | 类型 | 说明 |
|-------|------|------|
| `date` | DateTime | 交易日期 |
| `open` | Float | 开盘点数 |
| `high` | Float | 最高点数 |
| `low` | Float | 最低点数 |
| `close` | Float | 收盘点数 |
| `volume` | Float/Int | 成交手数 或 成交金额(万元) |

**指数选择**：
- 推荐使用 **上证综合指数** (000001.SH) 或 **上证 50** 或 **沪深 300**
- 一种指数即可，系统自动检测
- 时间范围必须覆盖所有股票的日期范围

**质量要求**：
- OHLCV 关系验证同股票（high >= close >= low）
- 日期与股票数据对齐（无额外缺失）
- volume 可以为 0（无需非空）

### 3.2 市场宽度数据（可选）

如果提供宽度数据，需要以下字段：

| 字段名 | 类型 | 范围 | 说明 |
|-------|------|------|------|
| `date` | DateTime | - | 交易日期 |
| `advance_count` | Int | >= 0 | 上涨股数 |
| `decline_count` | Int | >= 0 | 下跌股数 |
| `unchanged_count` | Int | >= 0 | 平盘股数 |
| `new_high_count` | Int | >= 0 | 创新高股数 |
| `new_low_count` | Int | >= 0 | 创新低股数 |
| `above_ma20_ratio` | Float | [0, 1] | 20日线上方股数占比 |
| `above_ma60_ratio` | Float | [0, 1] | 60日线上方股数占比 |
| `above_ma120_ratio` | Float | [0, 1] | 120日线上方股数占比 |
| `above_ma250_ratio` | Float | [0, 1] | 250日线上方股数占比 |
| `total_turnover` | Float | >= 0 | 总成交额(万元) 或 百万元 |

**处理方式**：
- 宽度数据可以缺失或部分缺失
- 如果缺失，系统标记 `market_data_available = False`
- 继续运行，但某些特性可能无法计算
- 不要填补缺失字段

### 3.3 CSV 格式示例

```csv
date,open,high,low,close,volume
2023-01-02,3500.50,3515.80,3485.20,3505.60,50000000
2023-01-03,3505.60,3520.40,3500.00,3515.80,48000000
...
```

---

## 4. 行业指数数据

### 4.1 必需字段

| 字段名 | 类型 | 说明 |
|-------|------|------|
| `date` | DateTime | 交易日期 |
| `sector` | String | 行业名称（见下表） |
| `open` | Float | 开盘点数 |
| `high` | Float | 最高点数 |
| `low` | Float | 最低点数 |
| `close` | Float | 收盘点数 |
| `volume` | Float/Int | 成交手数 或 成交金额 |

### 4.2 行业分类

推荐使用**国证行业分类（IRVT）**或**申万行业分类**，例如：

```
- 采矿业 (Mining)
- 制造业 (Manufacturing)
- 电力、热力、燃气及水生产和供应业 (Utilities)
- 建筑业 (Construction)
- 批发和零售业 (Wholesale & Retail)
- 交通运输、仓储和邮政业 (Transportation)
- 住宿和餐饮业 (Accommodation & Food)
- 信息传输、软件和信息技术服务业 (IT)
- 金融业 (Finance)
- 房地产业 (Real Estate)
- 租赁和商务服务业 (Leasing & Services)
- 科学研究和技术服务业 (Research & Tech)
- 水利、环境和公共设施管理业 (Public Utilities)
- 居民服务、修理和其他服务业 (Personal Services)
- 文化、体育和娱乐业 (Culture & Entertainment)
- 综合 (Conglomerate)
```

### 4.3 CSV 格式示例

```csv
date,sector,open,high,low,close,volume
2023-01-02,制造业,5000.50,5015.80,4985.20,5005.60,10000000
2023-01-02,金融业,3200.40,3210.60,3195.80,3205.50,8000000
2023-01-03,制造业,5005.60,5020.40,5000.00,5015.80,9800000
...
```

### 4.4 质量要求

- 同一日期每个行业只有一条记录
- 覆盖所有主要行业（至少 10 个）
- OHLCV 关系验证同股票
- 日期范围覆盖所有股票

---

## 5. 自由流通股数据

### 5.1 必需字段

| 字段名 | 类型 | 说明 |
|-------|------|------|
| `effective_date` | DateTime | 公告生效日期 |
| `symbol` | String | 股票代码 |
| `free_float_shares` | Int/Float | 自由流通股数 |

### 5.2 数据说明

**自由流通股定义**：
- 不包括战略性股东、控股股东的股份
- 可交易的流通股总数
- 单位：股（不是万股）

**effective_date**：
- 公告日期或生效日期
- 用于点对时间 (point-in-time) 过滤
- 同一标的可能有多条记录（不同时期）

**数据特性**：
- 更新频率低（通常为半年或全年）
- 历史记录可能很少（3-10 条/标的）
- 不能通过单一日期的 OHLCV 推断
- 缺失数据不能向前填补

### 5.3 CSV 格式示例

```csv
effective_date,symbol,free_float_shares
2023-01-15,000001,5000000000
2023-06-30,000001,5100000000
2024-01-20,000001,5050000000
2023-02-01,000002,3000000000
...
```

### 5.4 验证规则

```python
from mctr.data.validators import validate_free_float

df = pd.read_csv("free_float.csv", parse_dates=["effective_date"])
df["date"] = df["effective_date"]  # 日期列统一化
df = df.set_index("date")

try:
    validated = validate_free_float(df)
except ValueError as e:
    print(f"❌ 校验失败：{e}")
    # 若缺少此数据，继续运行但标记 incomplete
```

### 5.5 缺失处理

- ✓ **完全缺失**：标记 `chip_data_available = False`，继续运行
- ✓ **部分标的缺失**：为缺失的标的标记 `chip_data_available = False`，其他继续
- ✓ **数据过时**：使用最近的有效记录，不向前填补

---

## 6. 股东数据

### 6.1 必需字段

| 字段名 | 类型 | 范围 | 说明 |
|-------|------|------|------|
| `effective_date` | DateTime | - | 公告生效日期 |
| `symbol` | String | - | 股票代码 |
| `shareholder_id` | String | - | 股东标识符（唯一） |
| `shares` | Int/Float | >= 0 | 持股数（股） |
| `holder_type` | String | 见下表 | 股东类型 |
| `activity_weight` | Float | [0, 1] 或 None | 活跃度权重 |

### 6.2 股东类型

```
- "executive"        # 高管/董事
- "founder"          # 创始人
- "strategic"        # 战略投资者
- "institutional"    # 机构投资者
- "employee"         # 员工持股
- "other"            # 其他
```

### 6.3 activity_weight 说明

- **0.0～1.0**：显式权重（优先使用）
- **None/NaN**：使用默认权重（由 ChipConfig 提供）

**默认权重示例** (ChipConfig):
```python
{
    "executive": 0.9,      # 高管最活跃
    "founder": 0.95,       # 创始人最活跃
    "strategic": 0.3,      # 战略投资者较不活跃
    "institutional": 0.5,  # 机构投资者中等
    "employee": 0.6,       # 员工较活跃
    "other": 0.1,          # 其他最不活跃
}
```

### 6.4 CSV 格式示例

```csv
effective_date,symbol,shareholder_id,shares,holder_type,activity_weight
2023-12-31,000001,SH001,500000000,founder,0.95
2023-12-31,000001,SH002,300000000,institutional,0.5
2023-12-31,000001,SH003,200000000,employee,0.6
2024-06-30,000001,SH001,500000000,founder,0.95
...
```

### 6.5 验证规则

```python
from mctr.data.validators import validate_shareholder

df = pd.read_csv("shareholders.csv", parse_dates=["effective_date"])
df["date"] = df["effective_date"]
df = df.set_index("date")

try:
    validated = validate_shareholder(df)
    # validated 已按 effective_date 排序
except ValueError as e:
    print(f"❌ 校验失败：{e}")
```

### 6.6 缺失处理

- ✓ 完全缺失：标记 `chip_data_available = False`
- ✓ 部分标的缺失：为缺失的标的标记不完整
- ✓ 可以只有部分股东：系统加权剩余股份为"unknown"

---

## 7. 点对时间 (Point-in-Time) 要求

### 7.1 核心原则

**所有数据必须按 `as_of_date` 截断**：

```python
# 股票/市场/行业 OHLCV
date <= as_of_date

# 自由流通股
effective_date <= as_of_date
（取该标的最新的有效记录）

# 股东数据
effective_date <= as_of_date
（可能有多条，取最新的）
```

### 7.2 实现示例

```python
from mctr.data.snapshot import build_snapshot
import pandas as pd

# 为 2024-01-31 构建快照（不包含 2024-02-01 的数据）
snapshot = build_snapshot(
    symbol="000001",
    as_of_date=pd.Timestamp("2024-01-31"),
    stock_data=stock_df,  # date <= 2024-01-31
    market_index=market_df,  # date <= 2024-01-31
    sector_index=sector_df,  # date <= 2024-01-31
    free_float_data=ff_df,  # effective_date <= 2024-01-31
    shareholder_data=sh_df,  # effective_date <= 2024-01-31
)

# 验证
assert snapshot.stock_ohlcv.index.max() <= snapshot.as_of_date
assert snapshot.free_float is None or snapshot.free_float.empty or \
       snapshot.free_float.index.max() <= snapshot.as_of_date
```

### 7.3 禁止操作

🚫 **严格禁止**：
- `shift(-n)` 访问未来数据
- `bfill()` 向前填充
- `ffill()` 前向传播
- `fillna()` 填补缺失值
- 任何重新索引或 reindex 超出 as_of_date

### 7.4 缺失日期处理

```python
# ✓ 允许：报告缺失日期但不填补
report = quality_report(df, ...)
print(f"缺失日期：{report.missing_dates}")

# ❌ 禁止：
df = df.reindex(pd.date_range(df.index.min(), df.index.max(), freq='D'))

# ✓ 用户决定是否填补
if len(report.missing_dates) > 0:
    print("需要手动处理缺失日期")
    # 用户填补或确认跳过
```

---

## 8. 数据完整性检查清单

### 8.1 股票 OHLCV

- [ ] 格式：CSV 或 Parquet
- [ ] 包含列：date, symbol, open, high, low, close, volume
- [ ] 日期类型：datetime64[ns]
- [ ] 日期排序：升序，无重复
- [ ] OHLCV 关系：high >= close >= low, volume >= 0
- [ ] 标的数量：20-50 只（第一阶段）
- [ ] 时间范围：至少 2,500 个交易日（~10 年）
- [ ] 代码格式：6 位数字 (000001-999999)
- [ ] 复权状态：前复权

### 8.2 市场指数

- [ ] 格式：CSV 或 Parquet
- [ ] 包含列：date, open, high, low, close, volume
- [ ] 日期类型：datetime64[ns]
- [ ] 日期排序：升序，无重复
- [ ] 时间覆盖：与股票数据范围一致或更广
- [ ] OHLCV 关系：验证通过

### 8.3 行业指数

- [ ] 格式：CSV 或 Parquet
- [ ] 包含列：date, sector, open, high, low, close, volume
- [ ] 日期类型：datetime64[ns]
- [ ] 行业数量：至少 10 个
- [ ] 同日期行业唯一性：检验通过
- [ ] 时间覆盖：与股票数据范围一致或更广

### 8.4 自由流通股

- [ ] 格式：CSV 或 Parquet
- [ ] 包含列：effective_date, symbol, free_float_shares
- [ ] 日期类型：datetime64[ns]
- [ ] 数值范围：free_float_shares > 0
- [ ] 唯一性：(symbol, effective_date) 对唯一

### 8.5 股东数据

- [ ] 格式：CSV 或 Parquet
- [ ] 包含列：effective_date, symbol, shareholder_id, shares, holder_type, activity_weight
- [ ] 日期类型：datetime64[ns]
- [ ] shares >= 0
- [ ] activity_weight in [0, 1] or None
- [ ] holder_type 在允许列表中
- [ ] 唯一性：(effective_date, symbol, shareholder_id) 三元组唯一

---

## 9. 配置参数

### 9.1 ChipConfig

```python
from mctr.config import ChipConfig

config = ChipConfig(
    # 芯片浓度权重
    concentration_threshold=0.3,
    
    # 活跃度类型权重
    activity_weights={
        "executive": 0.9,
        "founder": 0.95,
        "strategic": 0.3,
        "institutional": 0.5,
        "employee": 0.6,
        "other": 0.1,
    },
    
    # 未知权重（覆盖未识别的股东）
    unknown_activity_weight=0.15,
)
```

### 9.2 BottomConfig

```python
from mctr.config import BottomConfig

config = BottomConfig(
    # 芯片距离衰减参数
    chip_distance_scale=0.10,  # 价格的 10%
    
    # Momentum 特征归一化尺度
    momentum_feature_scales={
        "macd": 1.0,
        "kdj": 1.0,
        "price_velocity": 1.0,
    },
    
    # L1-L4 阈值（不要修改）
    l1_threshold=0.45,
    l2_threshold=0.35,
    l3_threshold=0.55,
    l4_threshold=0.80,
    
    # 其他参数（参考 BottomConfig 文档）
)
```

---

## 10. 数据不完整情况处理

### 10.1 标记不完整

如果数据缺失，系统应标记可用性标志：

```python
snapshot = HistoricalDataSnapshot(
    ...,
    chip_data_available=False,  # 缺少自由流通股或股东数据
    market_data_available=False,  # 缺少市场数据
    sector_data_available=False,  # 缺少行业数据
)
```

### 10.2 验证层处理

```python
from mctr.validation.validator import HistoricalValidator

validator = HistoricalValidator()
result = validator.validate_symbol(
    symbol="000001",
    stock_data=df,
    ...,
)

# 输出中会包含可用性标志
print(f"Chip data available: {result.chip_data_available}")
print(f"Market data available: {result.market_data_available}")
```

### 10.3 降级运行

| 缺失数据 | 行为 | 影响 |
|--------|------|------|
| 自由流通股 + 股东 | 继续运行 | Phase 2 芯片数据不完整 |
| 市场宽度 | 继续运行 | Market Regime 某些特性无法计算 |
| 市场指数 | 拒绝 | 无法计算 Market Regime |
| 行业指数 | 拒绝 | 无法计算 Sector Regime |
| 股票 OHLCV | 拒绝 | 无法计算任何阶段 |

---

## 11. 数据源推荐

### 11.1 自行准备（最推荐）

如果有数据权限或内部数据：
- 直接导出为 CSV 或 Parquet
- 按本文档格式整理
- 通过校验器验证
- 存放在 `data/raw/` 目录

### 11.2 开源数据源

- **Tushare** (TuShare Pro)
  - https://www.tushare.pro/
  - 支持 A 股全量数据
  - 需要本地导出为 CSV

- **AkShare**
  - https://akshare.akfamily.xyz/
  - 免费 A 股历史数据
  - 支持 OHLCV、行业、宽度数据

- **网易财经**
  - https://quotes.money.163.com/
  - 免费但爬取限制

- **新浪财经** / **东方财富**
  - 爬取限制多
  - 不推荐用于模型

### 11.3 数据准备流程

```
步骤 1: 选择数据源（内部优先）
步骤 2: 导出数据为 CSV/Parquet
步骤 3: 放到 data/raw/ 目录
步骤 4: 运行校验器验证
步骤 5: 生成质量报告检查
步骤 6: 通过验收后进行分析
```

---

## 12. 验收标准

### 12.1 数据可用性

| 条件 | 状态 | 处理 |
|-----|------|------|
| OHLCV 完整 + Market + Sector | ✓ 可运行 | 进行完整验证 |
| OHLCV 完整 + Market + Sector | 但缺 FreeFloat/Shareholder | ✓ 可运行 | 标记不完整 |
| OHLCV + 缺失 Market 或 Sector | ✗ 拒绝 | 无法进行 Phase 3 |
| OHLCV 缺失 | ✗ 拒绝 | 无法进行任何分析 |

### 12.2 质量检查

```python
from mctr.data.validators import quality_report

# 验证后检查质量报告
report = quality_report(df, ...)

# 可接受范围
assert len(report.missing_columns) == 0, "缺列不可接受"
assert len(report.invalid_rows) == 0, "无效行不可接受"
assert len(report.duplicate_dates) == 0, "重复日期不可接受"

# 警告范围（记录但继续）
if report.missing_dates:
    print(f"⚠️ 警告：缺失 {len(report.missing_dates)} 个日期")
if report.future_rows:
    print(f"⚠️ 警告：发现 {len(report.future_rows)} 行未来数据（将被截断）")
```

---

## 13. 最终检查清单

- [ ] 数据源已选定
- [ ] 数据已导出为 CSV/Parquet
- [ ] 数据已存放在 `data/raw/` 目录
- [ ] 格式验证通过（数据类型、列名）
- [ ] OHLCV 关系验证通过
- [ ] 日期排序验证通过
- [ ] 唯一性验证通过（symbol-date/sector-date）
- [ ] 时间范围足够（>= 2,500 天）
- [ ] 股票数量足够（20-50 只）
- [ ] 质量报告生成完成
- [ ] 无致命错误（缺列、无效行等）
- [ ] 记录所有警告和不完整标记
- [ ] 准备进入 Step 3（数据适配器实现）

---

## 附录 A：常见问题

### Q1: 能否使用非复权价格？
**A**: 不能。系统假设所有 OHLCV 已前复权。如使用原始价格会导致结果错误。

### Q2: 自由流通股只有一条历史记录能用吗？
**A**: 可以。系统会为没有更新的标的使用最近的有效记录。

### Q3: 股东数据可以是空的吗？
**A**: 可以。会标记 `chip_data_available = False`，继续运行但 Phase 2 数据不完整。

### Q4: 市场指数可以用不同的指数吗（沪深 300 vs 上证 50）？
**A**: 可以。系统自动检测。建议全程使用同一指数。

### Q5: 能否修改 L1-L4 阈值来改进结果？
**A**: 本阶段禁止。这是**观察性验证**，不是优化阶段。任何模型修改需要后续通过设计评审。

### Q6: 缺失数据比例多少时应该拒绝？
**A**: 取决于用例。建议：
- 缺失日期 < 5%：可接受
- 缺失日期 5-10%：记录警告
- 缺失日期 > 10%：考虑拒绝

---

**文档版本**：1.0  
**最后更新**：2026-02-XX  
**状态**：✅ 数据层审计完成
