# 测试指南

本文档提供 Kurisu 项目当前功能的测试方法和步骤。

## 测试环境准备

### 1. 启动依赖服务

确保以下服务已启动：

```bash
# 启动 PostgreSQL
docker run -d --name kurisu-postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=kurisu \
  -p 5432:5432 \
  postgres:16-alpine

# 启动 Redis（可选，测试调度器需要）
docker run -d --name kurisu-redis \
  -p 6379:6379 \
  redis:7-alpine
```

### 2. 配置环境变量

```bash
cd backend
cp .env.example .env

# 编辑 .env 文件，配置数据库连接
# POSTGRES_SERVER=localhost
# POSTGRES_PASSWORD=password
# POSTGRES_DB=kurisu
```

### 3. 执行数据库迁移

```bash
source venv/bin/activate
alembic upgrade head
```

### 4. 同步市场数据

```bash
# 启动 API 服务（另一个终端）
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
# 触发市场同步（在另一个终端）
curl -X POST "http://localhost:8000/api/v1/markets/sync" \
  -H "Content-Type: application/json"
```

---

## 功能测试

### 测试 1: 数据库模型测试

**目标**: 验证 `DataSyncState` 模型及其新增字段

**步骤**:

1. 运行单元测试：

```bash
cd backend
source venv/bin/activate
pytest tests/test_sync_state.py -v
```

**预期结果**:
- 所有 4 个测试用例通过
- 测试覆盖：创建记录、状态转换、时间更新、状态查询

---

### 测试 2: 调度器启动测试

**目标**: 验证调度器能正常启动和关闭

**步骤**:

1. 启动应用并观察日志：

```bash
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**预期日志**:
```
INFO:     Performing startup checks...
INFO:     Database connection established.
INFO:     Redis connection established. (或: Redis job store unavailable, using memory store)
INFO:     Scheduler started successfully.
INFO:     Registered default scheduled jobs
```

2. 停止应用（Ctrl+C）

**预期日志**:
```
INFO:     Shutting down...
INFO:     Shutting down scheduler...
INFO:     Scheduler shut down successfully.
```

---

### 测试 3: 手动创建同步状态

**目标**: 验证数据库模型和 API 可以正常创建同步状态

**步骤**:

1. 获取一个市场 ID：

```bash
curl "http://localhost:8000/api/v1/markets?limit=1"
```

2. 记下返回的 `id`，假设为 `1`

3. 使用 Python 交互式环境创建同步状态：

```bash
source venv/bin/activate
python
```

```python
from app.core.database import SessionLocal
from app.models.sync_state import DataSyncState, SyncStatus
from datetime import datetime, timezone

async def create_test_sync_state():
    async with SessionLocal() as db:
        # 创建测试同步状态
        sync_state = DataSyncState(
            market_id=1,
            exchange="binance",
            symbol="BTC/USDT",
            timeframe="1h",
            is_auto_syncing=False,  # 先设为 False，避免自动触发
            sync_status=SyncStatus.IDLE,
        )
        db.add(sync_state)
        await db.commit()
        await db.refresh(sync_state)
        print(f"Created sync state: ID={sync_state.id}")
        print(f"Market ID: {sync_state.market_id}")
        print(f"Symbol: {sync_state.symbol}")
        print(f"Timeframe: {sync_state.timeframe}")
        print(f"Status: {sync_state.sync_status}")

import asyncio
asyncio.run(create_test_sync_state())
```

**预期结果**:
- 成功创建记录
- 输出显示正确的字段值

---

### 测试 4: 启用自动同步

**目标**: 验证自动同步开关功能

**步骤**:

1. 更新同步状态，启用自动同步：

```python
from app.core.database import SessionLocal
from app.models.sync_state import DataSyncState
from datetime import datetime, timezone

async def enable_auto_sync():
    async with SessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(DataSyncState).where(DataSyncState.market_id == 1)
        )
        sync_state = result.scalar_one()

        sync_state.is_auto_syncing = True
        sync_state.sync_status = SyncStatus.IDLE
        await db.commit()
        await db.refresh(sync_state)
        print(f"Enabled auto-syncing for {sync_state.symbol}/{sync_state.timeframe}")

import asyncio
asyncio.run(enable_auto_sync())
```

2. 等待调度器执行（默认 1 分钟）

3. 查看应用日志，应该看到：

```
INFO:     Starting auto-sync OHLCV job
INFO:     Found 1 sync states with auto-syncing enabled
DEBUG:    Syncing binance/BTC/USDT/1h from None
DEBUG:    Synced N rows for binance/BTC/USDT/1h
INFO:     Auto-sync OHLCV job completed
```

4. 查询同步状态：

```python
from app.core.database import SessionLocal
from app.models.sync_state import DataSyncState

async def check_sync_state():
    async with SessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(DataSyncState).where(DataSyncState.market_id == 1)
        )
        sync_state = result.scalar_one()
        print(f"Last sync time: {sync_state.last_sync_time}")
        print(f"Sync status: {sync_state.sync_status}")
        print(f"Error message: {sync_state.error_message}")

import asyncio
asyncio.run(check_sync_state())
```

**预期结果**:
- `last_sync_time` 有值
- `sync_status` 为 "idle" 或 "error"
- 如果有错误，`error_message` 有内容

---

### 测试 5: 并发控制测试

**目标**: 验证并发控制（Semaphore）是否工作

**步骤**:

1. 创建多个自动同步的记录：

```python
from app.core.database import SessionLocal
from app.models.sync_state import DataSyncState, SyncStatus

async def create_multiple_sync_states():
    async with SessionLocal() as db:
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "ADA/USDT"]
        for i, symbol in enumerate(symbols):
            sync_state = DataSyncState(
                market_id=i + 1,  # 假设市场 ID 存在
                exchange="binance",
                symbol=symbol,
                timeframe="1h",
                is_auto_syncing=True,
                sync_status=SyncStatus.IDLE,
            )
            db.add(sync_state)
        await db.commit()
        print(f"Created {len(symbols)} sync states")

import asyncio
asyncio.run(create_multiple_sync_states())
```

2. 观察应用日志

**预期结果**:
- 日志显示同时最多 3 个 sync 操作在执行（`MAX_CONCURRENT_SYNCS=3`）
- 完成一个后，下一个才开始

---

### 测试 6: 错误处理测试

**目标**: 验证错误被正确捕获和记录

**步骤**:

1. 创建一个不存在的市场 ID：

```python
from app.core.database import SessionLocal
from app.models.sync_state import DataSyncState, SyncStatus

async def create_error_case():
    async with SessionLocal() as db:
        sync_state = DataSyncState(
            market_id=99999,  # 不存在的 ID
            exchange="binance",
            symbol="FAKE/COIN",
            timeframe="1h",
            is_auto_syncing=True,
            sync_status=SyncStatus.IDLE,
        )
        db.add(sync_state)
        await db.commit()
        print("Created sync state with invalid market_id")

import asyncio
asyncio.run(create_error_case())
```

2. 等待调度器执行

3. 检查状态：

```python
from app.core.database import SessionLocal
from app.models.sync_state import DataSyncState

async def check_error_state():
    async with SessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(DataSyncState).where(DataSyncState.market_id == 99999)
        )
        sync_state = result.scalar_one()
        print(f"Sync status: {sync_state.sync_status}")
        print(f"Error message: {sync_state.error_message}")
        print(f"Last error time: {sync_state.last_error_time}")

import asyncio
asyncio.run(check_error_state())
```

**预期结果**:
- `sync_status` 为 "error"
- `error_message` 包含错误描述（如 "Market not found"）
- `last_error_time` 有值

---

### 测试 7: OHLCV 数据查询

**目标**: 验证数据同步后的查询功能

**步骤**:

1. 确保已同步数据（测试 4 或测试 5）

2. 查询 OHLCV 数据：

```bash
# 需要先获取 market_id
curl "http://localhost:8000/api/v1/data/ohlcv?market_id=1&timeframe=1h&start_time=2026-03-01T00:00:00Z&limit=10"
```

**预期结果**:
- 返回 OHLCV 数据数组
- 格式: `[[timestamp_ms, open, high, low, close, volume], ...]`

---

## 健康检查测试

### 测试 8: 健康检查端点

**步骤**:

```bash
curl "http://localhost:8000/health"
```

**预期结果**:
```json
{
  "status": "ok",
  "database": "connected",
  "redis": "connected" (或 "error" 如果 Redis 未启动)
}
```

---

## 调试建议

### 查看日志

增加日志级别查看详细信息：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level debug
```

### 数据库查询

直接连接数据库查看数据：

```bash
psql -h localhost -U postgres -d kurisu

# 查看同步状态
SELECT * FROM data_sync_state;

# 查看市场
SELECT id, exchange, symbol FROM markets LIMIT 5;

# 查看 OHLCV 数据
SELECT * FROM ohlcv WHERE market_id = 1 AND timeframe = '1h' ORDER BY time DESC LIMIT 5;
```

### 重置测试数据

```bash
# 删除同步状态数据
psql -h localhost -U postgres -d kurisu -c "DELETE FROM data_sync_state;"

# 重新开始测试
```

---

## 常见问题

### 问题 1: 调度器不执行任务

**原因**:
- 没有创建 `is_auto_syncing=True` 的记录
- `sync_status` 不是 "idle"
- Redis 不可用且未降级

**解决**:
- 检查 `data_sync_state` 表数据
- 查看应用日志中的调度器状态

### 问题 2: 数据库连接失败

**原因**:
- PostgreSQL 未启动
- 环境变量配置错误

**解决**:
```bash
# 检查 PostgreSQL 是否运行
docker ps | grep postgres

# 检查 .env 配置
cat .env
```

### 问题 3: API 限流错误

**原因**:
- 并发数设置过高
- 交易所 API 限制

**解决**:
- 降低 `MAX_CONCURRENT_SYNCS` 值
- 增加调度器执行间隔

---

## 下一步

完成基础测试后，可以：

1. 启用多个市场的时间周期进行测试
2. 测试长时间运行的稳定性
3. 监控数据库和 Redis 的性能
4. 继续实施 Step 3-6（API 接口、集成测试等）