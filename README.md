# MCTR

Multi-Cycle Trend & Chip Resonance，多周期趋势筹码共振择时模型。

## 第一阶段状态

当前仓库只实现研究计算核心和测试框架，不接入真实行情、券商、网页 UI、自动交易、爬虫或复杂数据库。

已实现：

- OHLCV 数据校验与统一接口
- 60/120/250/500 日滚动价格位置与价格分位计算
- MACD、MACD Histogram、Histogram Slope
- KDJ
- Price Velocity、Volume Velocity、Volume Exhaustion、Price Efficiency
- 基于趋势结构、方向效率和 MACD 柱体斜率的 Trend 状态基线
- ETC（Free Float × Active Ratio）和 Chip Density 数据契约
- Bottom/Top 特征、Risk Override、Resistance Zone、Risk/Reward 数据契约
- Market、Sector、Resonance 三层扩展契约
- S0-S5 策略状态枚举

## 第二阶段状态

已实现 ETC、股东活动权重、日期化限售股输入、OHLCV 价格重心近似的筹码密度、逐日筹码迁移、主筹码峰、核心筹码区间、集中度、支撑阻力、主峰迁移和价筹背离。详见 [docs/phase-two.md](docs/phase-two.md)。

## 未完成项目

Bottom/Top 概率引擎、Risk Override 计算、目标区校准及 point-in-time 回测引擎均标记为 TODO，尚未假装实现。

## 第三阶段状态

已实现 Market Regime、Market Breadth、Market Volume、Sector Regime、Relative Strength、Stock Regime Integration 和三层 Resonance。公式、门控、最弱环节约束及当前 Model Prior 说明见 [docs/phase-three.md](docs/phase-three.md)。Bottom/Top、Risk、回测和交易功能仍未实现。

## 第四阶段状态

已实现 Bottom Engine 的 Position、Chip、Exhaustion、Momentum Reversal、Trend Transition、Structural Score、Confirmation、Contradiction、Risk Override、Bottom Probability、L1-L4 和 Risk/Reward 原始计算。公式与边界见 [docs/phase-four.md](docs/phase-four.md)。当前没有 Top Engine、正式交易策略或历史校准。

## 第四阶段半验证状态

已实现 DataFrame 输入的历史信号验证、未来收益、MFE/MAE、L1-L4/Probability/Resonance 分组统计和案例分析接口。当前不接入真实历史数据；缺失数据会明确标记，不反向修改 Phase 1-4。详见 [docs/phase-four-five.md](docs/phase-four-five.md)。

## 开发

```bash
python -m pip install -e '.[dev]'
pytest
```

所有已实现的时间序列特征只读取当前及历史数据；数据不足时保留 `NaN`，不会静默填充未来值。
