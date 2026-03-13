# 仪表盘工作流指南

本文档说明当前仪表盘里市场、图表和回测页面的基础使用流程。

## 1. Markets 页面

路径：`/markets`

- 浏览已同步的交易对列表。
- 使用 `Sync` 按钮同步交易所市场元数据。
- 点击单行里的图表入口，会带着 `market_id`、`symbol` 和 `exchange` 跳到图表页。

## 2. Chart 页面

路径：`/chart?market_id=<id>&symbol=<pair>&exchange=<exchange>`

- 页面会按 `market_id` 拉取 OHLCV 数据，并通过 WebSocket 订阅实时更新。
- 顶部时间框架按钮会刷新当前图表周期，例如 `1h`、`4h`、`1d`。
- `7D`、`30D`、`90D` 快捷按钮可快速切换时间范围。
- 也可以直接修改 `Start Date` 和 `End Date`，图表会按新的区间重新拉取数据。
- `Backtest This Market` 按钮会把当前 `market_id`、`symbol`、`timeframe`、`start_date` 和 `end_date` 传给回测页。

如果 URL 里包含 `start_time` 和 `end_time`，图表页会使用这段时间范围，而不是默认的最近 30 天。

## 3. Backtest 页面

路径：`/backtest`

- 选择市场、策略、周期和日期范围后，点击 `Run Backtest` 执行回测。
- 市场选择现在以 `market_id` 为主，避免不同交易所的同名交易对冲突。
- 如果从图表页跳转过来，页面会自动预填 `market_id`、`timeframe`、`start_date` 和 `end_date`。

## 4. 从回测返回图表

回测页顶部的 `Open in Chart` 会带上：

- `market_id`
- `symbol`
- `exchange`
- `timeframe`
- `start_time`
- `end_time`

这样图表页会直接打开与当前回测一致的市场、周期和时间范围，方便对照价格走势和回测结果。
