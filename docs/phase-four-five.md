# MCTR Phase 4.5: Historical Validation Framework

## Validation Purpose

本阶段只验证冻结的 Phase 1-4 输出与未来事后标签之间的关系，不修改任何 Phase 1-4 数学定义，不做参数优化、机器学习或正式交易回测。

## Point-in-Time

验证输入是已经计算好的信号快照和 DataFrame OHLCV。T 日信号不会重新使用未来数据；未来数据只在验证标签阶段读取。没有股东、筹码、市场或行业历史数据时，不伪造输入，返回空结果或 `validation_data_incomplete`。

## Forward Return

对交易日 T 和 horizon N：

`forward_return_Nd = close[T+N] / close[T] - 1`

未来数据不足时返回 `None`，不使用最后价格补齐，不使用 `bfill`、`backfill`。

## MFE / MAE

只使用 T+1 到 T+N：

`MFE_N = max(high[T+1:T+N]) / close[T] - 1`

`MAE_N = min(low[T+1:T+N]) / close[T] - 1`

当前支持 MFE/MAE 20D、60D、120D。

## Statistics

`HistoricalValidator.statistics()` 分别按：

- L1、L2、L3、L4
- Probability buckets：0.0-0.2、0.2-0.4、0.4-0.6、0.6-0.8、0.8-1.0
- Resonance grade：A、B、C、D、NONE

输出每个 horizon 的 sample count、mean return、median return、win rate、mean MFE、mean MAE。统计只描述排序能力，不声称统计证明模型有效。

## Probability Calibration

Probability bucket 是固定报告分桶，不是校准后的概率解释。验证只观察 bucket 与未来 60D/120D/250D 收益是否单调，不根据结果反向调整模型。

## Resonance Validation

按 A/B/C/D/NONE 和调用方提供的共振强度分组，比较未来收益及 MFE/MAE。L4 与高/低共振的比较只作为探索性报告，不修改 Phase 3 Resonance。

## Three Case Study

支持长川科技（参考 2025-01-10）、恒铭达（参考 2025-01-10）、奥海科技（参考 2024-10-01）的 DataFrame 注入式案例分析。当前没有真实历史数据适配器，因此数据缺失时明确输出 `validation_data_incomplete`，不会伪造案例信号。存在数据时查找参考日前后约 30 个交易日窗口内首次 L2/L3/L4。

## Scope and Limitations

本阶段没有 Tushare、AkShare、Yahoo Finance、网络下载、API、数据库、爬虫、ML、参数拟合、Grid Search、正式 Backtest Engine、买卖、仓位、止损、止盈或资金曲线。Phase 1-4 保持冻结。验证结果只用于发现表现，不用于让结果变好看。
