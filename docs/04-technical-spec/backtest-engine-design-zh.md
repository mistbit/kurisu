# 策略与回测引擎设计 (Strategy & Backtest Engine Design)

本文档介绍 Kurisu 策略框架与回测引擎的设计与实现，覆盖数据模型、策略抽象、模拟撮合、绩效计算、API 集成与扩展方式。

## 1. 设计目标

- 提供通用的策略抽象，让开发者只需实现信号生成逻辑
- 事件驱动回测，按时间序列逐 bar 推进，贴近实盘执行语义
- 模拟真实交易摩擦（佣金、滑点、止损/止盈）
- 自动计算行业标准绩效指标（Sharpe、Sortino、最大回撤等）
- 通过 REST API 对前端暴露回测能力

## 2. 架构总览

回测系统由四个核心模块构成，层次关系如下：

```
┌───────────────────────────────────────────┐
│           BacktestEngine (编排层)           │
│  ┌─────────────┐  ┌────────────────────┐  │
│  │ BaseStrategy │  │ ExchangeSimulator  │  │
│  │  (策略层)    │  │   (撮合层)          │  │
│  └─────────────┘  └────────────────────┘  │
│                 ┌──────────────────────┐   │
│                 │ PerformanceCalculator│   │
│                 │    (统计层)          │   │
│                 └──────────────────────┘   │
└───────────────────────────────────────────┘
```

源文件对应关系：

| 模块 | 文件 | 行数 | 职责 |
|------|------|------|------|
| 策略抽象 | `backend/app/strategy/base.py` | 230 | 数据模型、策略基类、仓位计算 |
| 模拟撮合 | `backend/app/strategy/exchange_sim.py` | 430 | 订单执行、滑点佣金、止损止盈 |
| 回测引擎 | `backend/app/strategy/backtest.py` | 458 | 数据加载、事件循环、结果计算 |
| 示例策略 | `backend/app/strategy/examples.py` | 215 | MA 交叉、RSI 均值回归 |
| API 路由 | `backend/app/api/v1/backtest.py` | 158 | REST 端点 |

## 3. 数据模型

### 3.1 枚举类型

| 枚举 | 值 | 用途 |
|------|------|------|
| `OrderSide` | `buy`, `sell` | 订单方向 |
| `OrderType` | `market`, `limit`, `stop_loss`, `stop_limit` | 订单类型 |
| `SignalType` | `buy`, `sell`, `hold`, `exit_long`, `exit_short` | 信号类型 |

### 3.2 核心数据结构

#### OHLCVBar

单根 K 线，作为策略输入的最小数据单位：

| 字段 | 类型 | 说明 |
|------|------|------|
| `time` | `datetime` | K 线时间戳 |
| `open` | `float` | 开盘价 |
| `high` | `float` | 最高价 |
| `low` | `float` | 最低价 |
| `close` | `float` | 收盘价 |
| `volume` | `float` | 成交量 |

计算属性：`typical_price`（HLC 均价）、`range`（振幅）。

#### Signal

策略输出的交易信号：

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | `SignalType` | 信号方向 |
| `symbol` | `str` | 标的 |
| `time` | `datetime` | 信号时间 |
| `price` | `float?` | 指定价格（None 则市价） |
| `quantity` | `float?` | 指定数量（None 则由引擎决定） |
| `stop_loss` | `float?` | 止损价 |
| `take_profit` | `float?` | 止盈价 |
| `metadata` | `dict` | 策略自定义元信息 |

#### Position

当前持仓信息：

| 字段 | 类型 | 说明 |
|------|------|------|
| `symbol` | `str` | 标的 |
| `quantity` | `float` | 持仓数量 |
| `entry_price` | `float` | 均价 |
| `entry_time` | `datetime` | 建仓时间 |
| `side` | `OrderSide` | 多/空 |
| `unrealized_pnl` | `float` | 浮动盈亏 |
| `stop_loss` | `float?` | 止损 |
| `take_profit` | `float?` | 止盈 |

#### StrategyState

策略运行时状态容器：
- `cash`：可用资金
- `positions`：当前持仓映射
- `equity_curve`：权益曲线
- `trades`：已成交列表
- `current_prices`：最新价格
- 计算属性：`position_value`、`total_equity`

#### StrategyConfig

策略基础配置（Pydantic BaseModel）：

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `name` | `"BaseStrategy"` | 策略名称 |
| `symbols` | `[]` | 标的列表 |
| `timeframe` | `"1h"` | K 线周期 |
| `initial_capital` | `10000.0` | 初始资金 |
| `max_position_size` | `0.1` | 最大仓位比例 |
| `max_positions` | `5` | 最大持仓数 |
| `stop_loss_pct` | `None` | 全局止损百分比 |
| `take_profit_pct` | `None` | 全局止盈百分比 |
| `position_sizing` | `"fixed"` | 仓位计算方式 |

## 4. 策略抽象层（BaseStrategy）

### 4.1 生命周期

策略在回测期间的调用序列：

```
init()                          # 一次性初始化
  │
  ▼
on_bar(bar, symbol) ──► generate_signal(bar, symbol)   # 每根 K 线调用
  │                              │
  │                              ▼
  │                     Signal / None
  │
  ├─── (若有 Trade 成交) ──► on_trade(trade)
  │
  └─── 循环至数据结束
  │
  ▼
on_finish()                     # 回测结束收尾
```

### 4.2 关键接口

| 方法 | 说明 |
|------|------|
| `generate_signal(bar, symbol)` | **必须实现**。核心信号生成逻辑 |
| `init()` | 可选。初始化指标状态 |
| `on_bar(bar, symbol)` | 内部调用。维护历史、更新浮动盈亏后调用 `generate_signal` |
| `on_trade(trade)` | 成交回调。默认记录到 `state.trades` |
| `on_finish()` | 回测结束回调 |

### 4.3 数据访问辅助

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `get_history(symbol, length)` | `list[OHLCVBar]` | 最近 N 根 K 线 |
| `get_close_prices(symbol, length)` | `list[float]` | 最近 N 个收盘价 |
| `get_position(symbol)` | `Position?` | 当前持仓 |
| `has_position(symbol)` | `bool` | 是否持仓 |
| `get_equity()` | `float` | 当前权益 |
| `calculate_position_size(price, symbol)` | `float` | 按配置计算仓位大小 |

### 4.4 仓位计算方式

`calculate_position_size` 支持两种模式：

- `"fixed"`：固定比例 `equity * max_position_size / price`
- `"percent"`：百分比模式，可通过 `risk_pct` 参数覆盖

## 5. 模拟撮合层（ExchangeSimulator）

### 5.1 初始化参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `initial_capital` | `10000.0` | 初始资金 |
| `commission_rate` | `0.001` (0.1%) | 手续费率 |
| `slippage_rate` | `0.0005` (0.05%) | 滑点率 |
| `min_commission` | `1.0` | 最低手续费 |

### 5.2 订单执行逻辑

**市价单 (MARKET)**
- 以下一根 K 线 `open` 价 + 滑点成交
- 买入滑点上移，卖出滑点下移

**限价单 (LIMIT)**
- 买入：K 线 `low ≤ limit_price` 时成交
- 卖出：K 线 `high ≥ limit_price` 时成交
- 不加滑点（已指定价格）

**止损单 (STOP_LOSS)**
- `low ≤ stop_price` 触发，以 `stop_price` + 滑点成交

### 5.3 持仓管理

**开仓**
- 扣除资金 (`trade_value + commission`)
- 创建 `Position`（含均价计算）

**加仓**
- 数量加权平均计算新均价

**平仓**
- 计算已实现盈亏 `(fill_price - entry_price) * quantity - commission`
- 部分平仓：减少持仓数量
- 全部平仓：删除持仓

### 5.4 止损/止盈自动触发

每根 K 线处理完待执行订单后，检查所有持仓的 SL/TP：

1. **止损**：当 `bar.low ≤ stop_loss` 时，以 `stop_loss` + 滑点卖出
2. **止盈**：当 `bar.high ≥ take_profit` 时，以 `take_profit` 价卖出
3. 优先检查止损（同一 bar 内止盈不再触发）

### 5.5 信号到订单的映射

`process_signal()` 将策略信号转为订单：

| 信号类型 | 行为 |
|----------|------|
| `BUY` | 若无持仓则开仓（数量默认 10% 资金） |
| `SELL` | 若有持仓则平仓（数量默认全部） |
| `EXIT_LONG` | 全量平仓 |
| `HOLD` | 不操作 |

## 6. 回测引擎（BacktestEngine）

### 6.1 核心流程

```
load_data(symbol, bars)          # 1. 加载数据
     │
     ▼
run(start_date, end_date)        # 2. 启动回测
     │
     ├── strategy.init()         # 初始化策略
     ├── exchange.reset()        # 重置模拟器
     │
     ▼
  ┌──────────────────────────┐
  │  for (time, symbol, bar) │   # 3. 按时间序列遍历
  │    in _iterate_bars():   │
  │                          │
  │   strategy.on_bar()      │   信号生成
  │        │                 │
  │   exchange.process_bar() │   执行待处理订单
  │        │                 │
  │   exchange.process_signal│   处理新信号
  │        │                 │
  │   记录 trade & equity    │
  └──────────────────────────┘
     │
     ▼
  _calculate_results()           # 4. 计算绩效
     │
     ▼
  BacktestResult                 # 5. 返回结果
```

### 6.2 数据加载

两种方式：

- `load_data(symbol, bars: list[OHLCVBar])`：直接加载 Bar 对象
- `load_data_from_dict(symbol, data: list[dict])`：从字典列表加载

多标的支持：可多次调用 `load_data`，引擎内部将所有标的的 K 线按时间排序后统一迭代。

### 6.3 事件循环

`_iterate_bars()` 将所有标的的 K 线合并为 `(time, symbol, bar)` 元组，按时间升序排列。

每个 bar 的处理顺序：
1. **策略处理**：调用 `strategy.on_bar()` 产生信号
2. **订单撮合**：`exchange.process_bar()` 执行前一轮的待处理订单
3. **信号转换**：`exchange.process_signal()` 将新信号转为订单（下一 bar 撮合）
4. **状态记录**：记录成交、更新权益曲线

这种"信号生成 → 下一 bar 执行"的语义模拟了实盘中的信号延迟。

## 7. 绩效计算（PerformanceCalculator）

### 7.1 收益指标

| 指标 | 计算方式 |
|------|----------|
| `total_return` | `final_capital - initial_capital` |
| `total_return_pct` | `total_return / initial_capital * 100` |
| `annualized_return` | `(final / initial)^(1/years) - 1` |

### 7.2 风险指标

| 指标 | 说明 |
|------|------|
| Sharpe Ratio | $(R_p - R_f) / \sigma_p$，默认 $R_f = 2\%$，年化 252 个周期 |
| Sortino Ratio | 仅使用下行偏差替代标准差 |
| Max Drawdown | 峰值到谷值的最大跌幅百分比 |

### 7.3 交易统计

| 指标 | 说明 |
|------|------|
| `win_rate` | 盈利卖出 / 总卖出 |
| `profit_factor` | 总盈利 / 总亏损绝对值 |
| `avg_trade_return` | 每笔交易平均盈亏 |
| `winning_trades` | 盈利交易数 |
| `losing_trades` | 亏损交易数 |

统计仅基于 `side == "sell"` 的交易记录（即平仓交易），因为 PnL 在平仓时结算。

### 7.4 回测结果对象（BacktestResult）

`BacktestResult` 包含所有指标与详细数据：

- 基本信息：策略名、日期范围、初始/最终资金
- 绩效指标：上述所有指标
- 详细数据：`trades`（交易记录列表）、`equity_curve`、`drawdown_curve`
- 提供 `to_dict()` 方法用于 JSON 序列化

## 8. 内置策略

### 8.1 MA 交叉策略（MovingAverageCrossoverStrategy）

**配置（MAStrategyConfig）：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `short_period` | `10` | 快线周期 |
| `long_period` | `20` | 慢线周期 |

**信号逻辑：**
- 金叉（`prev_short ≤ prev_long && short_ma > long_ma`）→ 无持仓时 `BUY`
- 死叉（`prev_short ≥ prev_long && short_ma < long_ma`）→ 有持仓时 `SELL`
- 需要 `long_period + 1` 根 K 线才开始产生信号

### 8.2 RSI 均值回归策略（RSIStrategy）

**配置（RSIStrategyConfig）：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `rsi_period` | `14` | RSI 计算周期 |
| `oversold_threshold` | `30.0` | 超卖阈值 |
| `overbought_threshold` | `70.0` | 超买阈值 |

**信号逻辑：**
- RSI < `oversold_threshold` → 无持仓时 `BUY`（超卖买入）
- RSI > `overbought_threshold` → 有持仓时 `SELL`（超买卖出）

**RSI 计算：**
- SMA 方式：`RSI = 100 - 100 / (1 + avg_gain / avg_loss)`
- 需要 `rsi_period + 1` 根 K 线

## 9. API 集成

### 9.1 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/backtest/run` | POST | 执行回测 |
| `/api/v1/backtest/strategies` | GET | 列出可用策略 |

### 9.2 回测请求参数

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbol` | `str` | 是 | 交易标的（需数据库已有对应 Market） |
| `strategy` | `str` | 是 | 策略 ID（`ma_crossover` / `rsi`） |
| `start_date` | `str` | 是 | ISO 格式起始日期 |
| `end_date` | `str` | 是 | ISO 格式结束日期 |
| `initial_balance` | `float` | 否 | 初始资金（默认 10000） |
| `timeframe` | `str` | 否 | K 线周期（默认 `1h`） |
| `fast_period` | `int` | 否 | MA 策略快线周期 |
| `slow_period` | `int` | 否 | MA 策略慢线周期 |
| `rsi_period` | `int` | 否 | RSI 周期 |
| `rsi_oversold` | `float` | 否 | RSI 超卖阈值 |
| `rsi_overbought` | `float` | 否 | RSI 超买阈值 |

### 9.3 执行流程

1. 验证策略名称 → 解析日期
2. 从数据库查找 Market 记录
3. 通过 `ExchangeService` 从交易所实时拉取 OHLCV 数据
4. 实例化策略并注入参数
5. 创建 `BacktestEngine` 并执行
6. 格式化结果返回

### 9.4 返回数据

| 字段 | 说明 |
|------|------|
| `initial_balance` | 初始资金 |
| `final_balance` | 最终资金 |
| `total_return` | 总收益率 |
| `total_trades` | 总交易次数 |
| `winning_trades` / `losing_trades` | 盈/亏次数 |
| `win_rate` | 胜率 |
| `profit_factor` | 盈利因子 |
| `sharpe_ratio` | 夏普比率 |
| `sortino_ratio` | 索提诺比率 |
| `max_drawdown` | 最大回撤 |
| `trades` | 交易记录列表 |
| `equity_curve` | 权益曲线 |

## 10. 设计取舍与已知边界

### 10.1 主要取舍

| 决策 | 理由 |
|------|------|
| 事件驱动而非向量化 | 更接近实盘逻辑，便于加入状态管理和异步操作 |
| 市价单以下一 bar open 成交 | 避免未来数据偷看（look-ahead bias） |
| 统计仅 sell 侧计算 PnL | 针对做多策略的简化方案 |
| 回测 API 实时拉取数据 | 避免依赖本地存储，但增加了延迟 |

### 10.2 当前边界

| 边界 | 说明 |
|------|------|
| 仅支持做多 | 无做空持仓管理（`EXIT_SHORT` 信号存在但未实现） |
| 单标的回测 API | API 层面仅接受单个 symbol |
| 无参数优化 | 不支持参数扫描/网格搜索/遗传算法 |
| 无技术指标库 | MA/RSI 手动计算，无 ta-lib 集成 |
| 无策略持久化 | 策略实例不保存到数据库 |
| 固定 252 日年化 | 未根据实际 timeframe 自动调整年化周期数 |
| 回测数据来源 | API 端点从交易所实时拉取而非数据库 |

## 11. 扩展指南

### 11.1 新增策略

1. 在 `backend/app/strategy/examples.py`（或新文件）中：
   - 继承 `BaseStrategy`
   - 定义 `XxxStrategyConfig(StrategyConfig)` 配置类
   - 实现 `generate_signal(bar, symbol) -> Optional[Signal]`
   
2. 在 `backend/app/api/v1/backtest.py` 中：
   - 将策略类注册到 `STRATEGIES` 字典
   - 在 `BacktestRequest` 中添加新策略所需参数

3. 补充测试

### 11.2 可改进方向

| 方向 | 建议 |
|------|------|
| 技术指标 | 集成 `pandas-ta` 或 `ta-lib` 减少重复计算 |
| 参数优化 | 增加网格搜索/遗传算法模块 |
| 多标的组合 | 扩展 API 支持 `symbols: list[str]` |
| 做空支持 | 完善 `EXIT_SHORT` 逻辑和负数持仓管理 |
| 回测数据源 | 优先使用数据库已有 OHLCV，减少 API 调用 |
| 年化周期 | 根据 timeframe 自动推算 `periods_per_year` |
| 策略持久化 | 将回测参数和结果存入 `strategy_runs` 表 |

---

关联文档：

- [项目现状报告](../project-status.md)
- [数据库模式设计](database-schema-design-zh.md)
- [调度器系统设计](scheduler-system-design-zh.md)
