# ORM 模型实现方案 (ORM Model Implementation Plan)

本文档用于指导数据库设计向 SQLAlchemy ORM 模型落地的实现步骤与约定，不包含具体代码，仅定义实现边界、字段映射、关系与迁移注意事项。

相关参考：
- [数据库模式设计](database-schema-design-zh.md)

## 1. 目标与范围
- 将数据库设计文档中的核心表转化为 SQLAlchemy ORM 模型
- 明确字段类型、主键/外键、索引与约束
- 明确 TimescaleDB Hypertable 相关表的建表与迁移要求
- 输出可执行的迁移路径与验证清单

## 2. 依赖与前置条件
- PostgreSQL + TimescaleDB 环境已就绪
- 后端已使用 SQLAlchemy + Alembic + asyncpg
- 统一时区使用 TIMESTAMPTZ
- 数值字段统一使用高精度 Numeric

## 3. 模型与表的映射清单

### 3.1 元数据与配置类表
- markets → Market
- accounts → Account
- strategies → Strategy

### 3.2 时序与交易类表
- ohlcv → OHLCV (Hypertable)
- trades → Trade (Hypertable)
- orders → Order
- executions → Execution
- positions → Position (可作为快照表，建议按时间分区的普通表或 Hypertable)
- balances → Balance (可作为快照表，建议按时间分区的普通表或 Hypertable)

### 3.3 风控与运行态
- strategy_runs → StrategyRun
- risk_events → RiskEvent

## 4. 字段类型与精度约定
- 金额与价格统一使用 Numeric(20,10) 为默认精度
- 若部分交易所需要更高精度，可通过 Numeric(28,12) 或 Numeric(38,18) 提升
- 时间字段一律使用 TIMESTAMPTZ
- 字符串字段使用合理长度限制，如 50/100/255
- JSONB 字段用于可扩展元信息 (建议针对高频查询字段建立 GIN 索引)
- 枚举字段建议在数据库层使用 String 类型，在应用层使用 Enum 类进行校验，以方便后续扩展

## 5. 关系与约束设计

### 5.1 主键策略
- markets: 自增整数主键
- ohlcv: 复合主键 (time, market_id, timeframe)
- trades: 复合主键 (time, market_id, trade_id)
- orders: bigint 自增主键
- executions: bigint 自增主键
- positions: 复合主键 (time, market_id, strategy_id, account_id)
- balances: 复合主键 (time, asset, account_id)
- strategies / accounts / strategy_runs / risk_events: 自增主键或 bigint

### 5.2 外键关系
- ohlcv.market_id → markets.id
- trades.market_id → markets.id
- orders.market_id → markets.id
- orders.account_id → accounts.id
- orders.strategy_id → strategies.id
- executions.order_id → orders.id
- positions.market_id → markets.id
- positions.strategy_id → strategies.id
- positions.account_id → accounts.id
- balances.account_id → accounts.id
- strategy_runs.strategy_id → strategies.id
- risk_events.strategy_id → strategies.id
- risk_events.account_id → accounts.id
- risk_events.market_id → markets.id

### 5.3 唯一性与索引建议
- markets: (exchange, symbol) 唯一
- ohlcv: (market_id, timeframe, time DESC) 索引
- trades: (market_id, time DESC) 索引
- orders: (account_id, status), (strategy_id, status) 索引
- executions: (order_id, time DESC) 索引
- positions/balances: (account_id, time DESC) 索引

## 6. TimescaleDB 高级特性策略 (优化建议)

### 6.1 Hypertable 配置
- **ohlcv**: 
  - 必须启用 Hypertable
  - 建议启用压缩 (Compression)，按 (market_id, timeframe) 分组，按 time 排序
  - 建议设置压缩段时长 (compress_chunk_time_interval)
- **trades**:
  - 必须启用 Hypertable
  - 数据量极大，建议启用压缩，按 market_id 分组
- **positions / balances**:
  - 建议启用 Hypertable 以存储历史快照
  - 配合 `last()` 函数查询最新状态，或者维护一张独立的 `current_positions` 表

### 6.2 数据保留 (Retention)
- 建议配置数据保留策略 (Retention Policy)
- 比如 Trades 数据保留 1 年，OHLCV 数据保留 5-10 年
- 开发初期可暂时不开启自动删除

## 7. 目录结构与文件组织建议
- backend/app/models/
  - market.py
  - ohlcv.py
  - trade.py
  - order.py
  - execution.py
  - position.py
  - balance.py
  - strategy.py
  - strategy_run.py
  - risk_event.py
  - account.py
  - __init__.py

## 8. 验证清单
- 表是否创建成功
- 复合主键是否按设计生效
- 外键是否生效且可追溯
- Hypertable 是否成功创建
- 索引是否按设计生成
- 精度字段是否满足数据要求

## 9. 下一步落地顺序建议
- 定义基础表：markets, accounts, strategies
- 定义交易业务表：orders, executions
- 定义时序表：ohlcv, trades
- 定义快照表：positions, balances
- 定义运行与风控表：strategy_runs, risk_events
- 生成并修正迁移脚本
