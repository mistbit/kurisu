# 数据库层重构与实现计划

根据最新的数据库设计文档（`docs/04-technical-spec/database-schema-design-zh.md`），我们需要重新构建后端的数据模型层。以下是详细的实施步骤。

## 1. 基础架构恢复 (Infrastructure)

目前 `app/core/database.py` 中缺少 SQLAlchemy 的 `Base` 类定义，这是 ORM 模型的基础。

- [ ] **恢复 `Base` 类**：在 `app/core/database.py` 中添加 `DeclarativeBase` 定义。
  ```python
  from sqlalchemy.orm import DeclarativeBase

  class Base(DeclarativeBase):
      pass
  ```
- [ ] **配置 Alembic 环境**：检查 `alembic/env.py`，确保它能正确导入 `Base` 和所有模型元数据（`target_metadata`）。

## 2. 模型实现 (Model Implementation)

我们将根据实体关系，将模型拆分到不同的文件中，保持代码整洁。

- [ ] **创建 `app/models/market.py`**：
  - `Market`: 市场元数据
  - `OHLCV`: K线数据（TimescaleDB Hypertable）
  - `Trade`: 逐笔成交数据（TimescaleDB Hypertable）
- [ ] **创建 `app/models/account.py`**：
  - `Account`: 账户信息
  - `Balance`: 账户余额快照
  - `Position`: 持仓快照
- [ ] **创建 `app/models/order.py`**：
  - `Order`: 订单管理
  - `Execution`: 成交明细
- [ ] **创建 `app/models/strategy.py`**：
  - `Strategy`: 策略定义
  - `StrategyRun`: 策略运行实例
  - `RiskEvent`: 风控事件
- [ ] **更新 `app/models/__init__.py`**：
  - 导出所有模型类，方便 Alembic 自动发现。

## 3. 数据库迁移 (Migration)

这是关键步骤，因为 TimescaleDB 的特性（Hypertable、压缩、保留策略）不能通过 Alembic 自动生成，必须手动添加。

### 3.1 准备工作

- [ ] **确保 TimescaleDB 扩展已安装**：在数据库中执行 `CREATE EXTENSION IF NOT EXISTS timescaledb;`。
- [ ] **生成初始迁移脚本**：
  ```bash
  alembic revision --autogenerate -m "init_schema_with_timescaledb"
  ```

### 3.2 手动编辑迁移脚本

- [ ] **创建枚举类型**：在 `upgrade()` 函数中，**在创建表之前**，添加枚举类型定义：
  ```python
  # 创建枚举类型
  op.execute("CREATE TYPE timeframe_enum AS ENUM ('1m', '5m', '15m', '1h', '4h', '1d')")
  op.execute("CREATE TYPE order_side_enum AS ENUM ('buy', 'sell')")
  op.execute("CREATE TYPE order_type_enum AS ENUM ('limit', 'market', 'stop_loss', 'take_profit')")
  op.execute("CREATE TYPE order_status_enum AS ENUM ('open', 'closed', 'canceled', 'failed')")
  op.execute("CREATE TYPE taker_maker_enum AS ENUM ('taker', 'maker')")
  op.execute("CREATE TYPE run_type_enum AS ENUM ('backtest', 'live')")
  op.execute("CREATE TYPE run_status_enum AS ENUM ('running', 'completed', 'failed')")
  ```
  
- [ ] **创建表结构**：Alembic 自动生成的表结构，确保使用枚举类型。

- [ ] **创建索引**：在创建表之后，添加索引：
  ```python
  # OHLCV 索引
  op.create_index('idx_ohlcv_market_timeframe_time_desc', 'ohlcv', ['market_id', 'timeframe', sa.text('time DESC')])
  op.create_index('idx_ohlcv_market_time_desc', 'ohlcv', ['market_id', sa.text('time DESC')])
  
  # Trades 索引
  op.create_index('idx_trades_market_time_desc', 'trades', ['market_id', sa.text('time DESC')])
  
  # Executions 索引
  op.create_index('idx_executions_time', 'executions', ['time'])
  ```

- [ ] **创建唯一约束**：
  ```python
  # Markets 唯一约束
  op.create_unique_constraint('uix_exchange_symbol', 'markets', ['exchange', 'symbol'])
  
  # Accounts 唯一约束
  op.create_unique_constraint('uix_exchange_name', 'accounts', ['exchange', 'name'])
  
  # Trades 唯一约束
  op.create_unique_constraint('unique_trades_market_trade_id', 'trades', ['market_id', 'trade_id'])
  
  # Executions 唯一约束
  op.create_unique_constraint('unique_executions_order_trade_id', 'executions', ['order_id', 'trade_id'])
  ```

- [ ] **配置 TimescaleDB Hypertable**：
  ```python
  # OHLCV Hypertable
  op.execute("SELECT create_hypertable('ohlcv', 'time', if_not_exists => TRUE)")
  op.execute("""
      ALTER TABLE ohlcv SET (
          timescaledb.compress,
          timescaledb.compress_segmentby = 'market_id,timeframe',
          timescaledb.compress_orderby = 'time DESC'
      )
  """)
  op.execute("SELECT add_compression_policy('ohlcv', INTERVAL '7 days')")
  op.execute("SELECT add_retention_policy('ohlcv', INTERVAL '1 year')")
  
  # Trades Hypertable
  op.execute("SELECT create_hypertable('trades', 'time', if_not_exists => TRUE)")
  op.execute("""
      ALTER TABLE trades SET (
          timescaledb.compress,
          timescaledb.compress_segmentby = 'market_id',
          timescaledb.compress_orderby = 'time DESC'
      )
  """)
  op.execute("SELECT add_compression_policy('trades', INTERVAL '3 days')")
  op.execute("SELECT add_retention_policy('trades', INTERVAL '30 days')")
  ```

- [ ] **创建 Continuous Aggregates**：
  ```python
  # 创建 1小时 K线聚合视图
  op.execute("""
      CREATE MATERIALIZED VIEW ohlcv_1h
      WITH (timescaledb.continuous) AS
      SELECT time_bucket('1 hour', time) AS bucket,
             market_id,
             first(open, time) AS open,
             max(high) AS high,
             min(low) AS low,
             last(close, time) AS close,
             sum(volume) AS volume
      FROM ohlcv
      WHERE timeframe = '1m'
      GROUP BY bucket, market_id
  """)
  
  # 配置刷新策略
  op.execute("""
      SELECT add_continuous_aggregate_policy('ohlcv_1h',
          start_offset => INTERVAL '7 days',
          end_offset => INTERVAL '1 hour',
          schedule_interval => INTERVAL '10 minutes')
  """)
  ```

### 3.3 回滚脚本

- [ ] **编写 `downgrade()` 函数**：
  ```python
  def downgrade():
      # 删除 Continuous Aggregates
      op.execute("DROP MATERIALIZED VIEW IF EXISTS ohlcv_1h")
      
      # 删除 Hypertable（会自动删除相关策略）
      op.execute("DROP TABLE IF EXISTS trades")
      op.execute("DROP TABLE IF EXISTS ohlcv")
      
      # 删除其他表
      # ... (Alembic 自动生成)
      
      # 删除枚举类型
      op.execute("DROP TYPE IF EXISTS run_status_enum")
      op.execute("DROP TYPE IF EXISTS run_type_enum")
      op.execute("DROP TYPE IF EXISTS taker_maker_enum")
      op.execute("DROP TYPE IF EXISTS order_status_enum")
      op.execute("DROP TYPE IF EXISTS order_type_enum")
      op.execute("DROP TYPE IF EXISTS order_side_enum")
      op.execute("DROP TYPE IF EXISTS timeframe_enum")
  ```

## 4. 验证与测试 (Verification)

### 4.1 应用迁移

- [ ] **应用迁移**：
  ```bash
  alembic upgrade head
  ```

### 4.2 数据库结构验证

- [ ] **验证表创建**：
  ```sql
  \dt
  ```
- [ ] **验证 Hypertable**：
  ```sql
  SELECT hypertable_name FROM timescaledb_information.hypertables;
  ```
- [ ] **验证 Continuous Aggregates**：
  ```sql
  SELECT view_name FROM timescaledb_information.continuous_aggregates;
  ```
- [ ] **验证压缩策略**：
  ```sql
  SELECT hypertable_name, compression_state FROM timescaledb_information.compression_settings;
  ```

### 4.3 CRUD 测试

- [ ] **创建测试脚本** `tests/test_models.py`：
  ```python
  import asyncio
  from sqlalchemy.ext.asyncio import AsyncSession
  from app.core.database import SessionLocal
  from app.models import Market, OHLCV
  from datetime import datetime, timezone
  
  async def test_crud():
      async with SessionLocal() as session:
          # 测试 Market 创建
          market = Market(
              exchange='binance',
              symbol='BTC/USDT',
              base_asset='BTC',
              quote_asset='USDT',
              active=True
          )
          session.add(market)
          await session.commit()
          
          # 测试 OHLCV 创建
          ohlcv = OHLCV(
              time=datetime.now(timezone.utc),
              market_id=market.id,
              timeframe='1m',
              open=50000.0,
              high=51000.0,
              low=49500.0,
              close=50500.0,
              volume=100.5
          )
          session.add(ohlcv)
          await session.commit()
          
          print("✅ CRUD 测试成功")
  
  if __name__ == "__main__":
      asyncio.run(test_crud())
  ```

### 4.4 性能测试

- [ ] **插入性能测试**：批量插入 10000 条 OHLCV 数据，测试写入性能。
- [ ] **查询性能测试**：查询最近 1 小时的 K 线数据，测试查询性能。
- [ ] **压缩效果验证**：检查压缩后的存储空间占用。

## 5. 错误处理与回滚计划

- [ ] **备份现有数据**：如果数据库中已有数据，先进行备份。
- [ ] **准备回滚脚本**：确保 `downgrade()` 函数可以正确回滚所有更改。
- [ ] **测试回滚**：在测试环境中验证回滚流程。

## 6. 后续优化建议

- [ ] **监控与告警**：配置 TimescaleDB 的监控指标。
- [ ] **数据备份策略**：配置定期备份计划。
- [ ] **查询优化**：根据实际查询模式调整索引。

## 下一步行动建议

建议按照上述顺序，从 **1. 基础架构恢复** 开始执行。每个阶段完成后，进行验证再进入下一阶段。
