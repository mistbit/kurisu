# 自动同步与回补断点实施计划

本文档描述**方案 A：完善数据接入能力**的详细实施步骤。

## 目标

1. 引入定时任务调度器，实现自动化数据同步
2. 实现回补断点记录，避免每次全量重跑
3. 提供管理接口控制数据同步任务

---

## 1. 数据库模型扩展

### 1.1 创建 `DataSyncState` 模型

新增 `data_sync_state` 表，记录每个交易对和周期的同步状态：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| exchange | String(50) | 交易所标识 |
| symbol | String(50) | 交易对符号 |
| timeframe | String(10) | 时间周期 (1m, 5m, 1h, 1d 等) |
| **market_id** | Integer | 外键，关联 markets.id（优化查询性能） |
| **sync_status** | String(20) | 同步状态：idle, syncing, error |
| **error_message** | String(500) | 错误信息（最近一次失败的错误） |
| **last_error_time** | DateTime(timezone=True) | 最后错误时间 |
| last_sync_time | DateTime(timezone=True) | 最后同步时间（UTC） |
| backfill_completed_until | DateTime(timezone=True) | 历史数据回补完成时间 |
| is_auto_syncing | Boolean | 是否正在自动同步 |
| created_at | DateTime(timezone=True) | 创建时间 |
| updated_at | DateTime(timezone=True) | 更新时间 |

**唯一约束**: `(exchange, symbol, timeframe)`

**索引**: `market_id`, `last_sync_time`, `backfill_completed_until`, `sync_status`, `is_auto_syncing`

**外键**: `market_id -> markets.id`

### 1.2 创建 Alembic 迁移

```
alembic revision -m "add data_sync_state table"
```

---

## 2. 定时任务调度器

### 2.1 技术选型

使用 **APScheduler** (Advanced Python Scheduler)：

- 轻量级，无需额外的 worker 进程
- 内置持久化支持（可选）
- 支持多种触发器：interval, cron, date
- 与 FastAPI 集成简单

### 2.2 安装依赖

```bash
pip install apscheduler[redis]
```

### 2.3 调度器架构

在 `backend/app/scheduler/` 目录下创建：

```
app/scheduler/
├── __init__.py
├── scheduler.py      # APScheduler 实例管理
├── jobs.py           # 定义定时任务
└── state.py          # 任务状态管理
```

### 2.4 核心任务

#### 2.4.1 自动同步任务 (`auto_sync_ohlcv`)

- **频率**: 每 1 分钟（可配置）
- **逻辑**:
  1. 查询 `data_sync_state` 表中 `is_auto_syncing = True` 且 `sync_status = idle` 的记录
  2. 使用并发控制（Semaphore）限制同时处理的数量（避免 API 限流）
  3. 对每个记录：
     - 更新状态为 `syncing`
     - 复用缓存的 ExchangeService 连接
     - 从 `last_sync_time + 1秒` 开始获取最新 OHLCV 数据
     - 获取数据库中最后一条记录的时间作为新的 `last_sync_time`
     - 更新状态为 `idle` 或 `error`
  4. 捕获异常并记录到 `error_message`

#### 2.4.2 市场元数据同步任务 (`sync_markets`)

- **频率**: 每天 00:00
- **逻辑**: 调用现有的 `MarketService.sync_markets()`

#### 2.4.3 回补检查任务 (`check_backfill_gaps`)

- **频率**: 每小时
- **逻辑**: 检查是否有数据缺口，自动触发回补

### 2.5 集成到 FastAPI

在 `app/main.py` 的 `lifespan` 中：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    scheduler.start()
    yield
    # 关闭时
    scheduler.shutdown()
```

---

## 3. 回补断点实现

### 3.1 DataSyncState 服务

在 `app/services/` 创建 `sync_state_service.py`：

```python
class SyncStateService:
    # 获取同步状态
    async def get_state(market_id: int, timeframe: str) -> Optional[DataSyncState]

    # 更新同步状态
    async def update_last_sync_time(market_id: int, timeframe: str, time: datetime)

    # 标记回补完成
    async def mark_backfill_completed(market_id: int, timeframe: str, until: datetime)

    # 启用/禁用自动同步
    async def set_auto_syncing(market_id: int, timeframe: str, enabled: bool)

    # 获取所有待回补的记录
    async def get_pending_backfills() -> list[DataSyncState]
```

### 3.2 修改 MarketDataService

在 `fetch_ohlcv_history` 中集成断点逻辑：

1. 开始前查询 `last_sync_time` 或 `backfill_completed_until`
2. 从断点时间开始获取数据
3. 完成后更新同步状态

### 3.3 智能回补策略

- **首次回补**: 从当前时间往前推，一次性回补指定范围（如近 30 天）
- **增量回补**: 从最后一次记录开始
- **缺口回补**: 检测数据缺口并自动填充

---

## 4. API 接口扩展

### 4.1 同步状态查询

```
GET /api/v1/data/sync_state
```

**查询参数**:
- `market_id`: 过滤特定市场
- `timeframe`: 过滤特定周期
- `sync_status`: 过滤同步状态 (idle, syncing, error)
- `auto_syncing_only`: 仅返回正在自动同步的
- `has_errors`: 仅返回有错误的记录

**响应示例**:
```json
{
  "items": [
    {
      "id": 1,
      "market_id": 1,
      "exchange": "binance",
      "symbol": "BTC/USDT",
      "timeframe": "1h",
      "sync_status": "idle",
      "last_sync_time": "2026-03-03T10:00:00Z",
      "backfill_completed_until": "2026-02-01T00:00:00Z",
      "is_auto_syncing": true,
      "error_message": null,
      "last_error_time": null
    }
  ],
  "total": 1
}
```

### 4.2 手动触发回补

```
POST /api/v1/data/backfill
```

**请求体**:
```json
{
  "market_id": 1,
  "timeframes": ["1h", "4h", "1d"],
  "start_time": "2026-01-01T00:00:00Z",
  "end_time": "2026-03-01T00:00:00Z"
}
```

**响应**:
```json
{
  "task_id": "backfill_123",
  "status": "started",
  "message": "Backfill task queued for 3 timeframes"
}
```

### 4.3 启动/停止自动同步

```
POST /api/v1/data/auto_sync
```

**请求体**:
```json
{
  "market_id": 1,
  "timeframes": ["1h", "4h", "1d"],
  "enabled": true
}
```

### 4.4 查询调度器状态

```
GET /api/v1/scheduler/status
```

**响应**:
```json
{
  "running": true,
  "jobs": [
    {
      "id": "auto_sync_ohlcv",
      "name": "Auto Sync OHLCV",
      "next_run_time": "2026-03-03T10:01:00Z"
    }
  ]
}
```

---

## 5. 任务实施顺序

### Step 1: 数据库模型（1-2 小时）
- [ ] 创建 `DataSyncState` SQLAlchemy 模型
- [ ] 编写并执行 Alembic 迁移
- [ ] 编写模型测试

### Step 2: 调度器基础（2-3 小时）
- [ ] 安装 APScheduler 并更新 `requirements.txt`
- [ ] 创建 `app/scheduler/` 目录结构
- [ ] 实现 `scheduler.py` 基础框架
- [ ] 集成到 FastAPI lifespan

### Step 3: 同步状态服务（2-3 小时）
- [ ] 实现 `SyncStateService`
- [ ] 添加数据库索引优化
- [ ] 编写服务单元测试

### Step 4: 定时任务实现（3-4 小时）
- [ ] 实现 `auto_sync_ohlcv` 任务
- [ ] 实现 `sync_markets` 任务
- [ ] 添加错误处理和重试逻辑
- [ ] 编写任务测试

### Step 5: API 接口（2-3 小时）
- [ ] 实现 `GET /api/v1/data/sync_state`
- [ ] 实现 `POST /api/v1/data/backfill`
- [ ] 实现 `POST /api/v1/data/auto_sync`
- [ ] 实现 `GET /api/v1/scheduler/status`
- [ ] 编写 API 集成测试

### Step 6: 集成与测试（2-3 小时）
- [ ] 端到端测试完整流程
- [ ] 测试断点恢复功能
- [ ] 测试错误场景（网络异常、API 限流等）
- [ ] 更新文档

**预计总工时**: 12-18 小时

---

## 6. 优化记录

### 已完成的优化（2026-03-03）

#### 6.1 数据库模型优化
- 添加 `market_id` 外键字段，提升查询性能
- 添加 `sync_status` 字段跟踪同步状态（idle, syncing, error）
- 添加 `error_message` 和 `last_error_time` 字段记录错误信息
- 添加相关索引优化查询速度

#### 6.2 并发控制
- 使用 `asyncio.Semaphore` 限制并发 API 调用数量（默认 3）
- 避免触发交易所 API 限流
- 配置化：`MAX_CONCURRENT_SYNCS` 环境变量

#### 6.3 ExchangeService 连接复用
- 实现 ExchangeService 缓存机制
- 同一交易所的同步操作共享连接
- 应用关闭时自动清理缓存连接

#### 6.4 调度器健壮性
- Redis 连接失败时自动降级到内存存储
- 应用关闭时清理所有 ExchangeService 连接
- 错误信息持久化到数据库

#### 6.5 代码结构优化
- `SyncStatus` 常量类定义同步状态
- 优化 `state.py` 函数签名，使用 `market_id` 代替 `(exchange, symbol)`
- 更新测试覆盖新增字段和状态

---

## 7. 当前进度

### 已完成
- ✅ Step 1: 数据库模型（基础）
- ✅ Step 2: 调度器基础
- ✅ 代码优化（模型增强、并发控制、连接复用）

### 待完成
- ⏳ Step 3: 同步状态服务
- ⏳ Step 4: 定时任务实现
- ⏳ Step 5: API 接口
- ⏳ Step 6: 集成测试

---

## 6. 配置参数

在 `app/core/config.py` 中添加调度器配置：

```python
# Scheduler
SCHEDULER_ENABLED: bool = True
AUTO_SYNC_INTERVAL_MINUTES: int = 1
MARKET_SYNC_HOUR: int = 0  # 每天几点同步市场数据
BACKFILL_CHECK_INTERVAL_HOURS: int = 1
```

---

## 7. 注意事项

1. **并发控制**: 多个回补任务同时运行时需要控制并发数
2. **API 限流**: 需要实现速率限制，避免被交易所封禁
3. **错误恢复**: 任务失败后需要自动重试机制
4. **日志记录**: 详细记录同步过程，便于排查问题
5. **监控指标**: 记录同步成功率、延迟等指标
