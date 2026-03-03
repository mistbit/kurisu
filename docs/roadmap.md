# Kurisu 项目后续任务规划

本文档描述 Kurisu 项目后续开发的任务规划、技术方案和实施步骤。

---

## 当前状态

### 已完成
- ✅ Step 1: 数据库模型（`DataSyncState` 表）
- ✅ Step 2: 调度器基础（APScheduler 集成）
- ✅ 代码优化（`market_id` 外键、并发控制、连接复用、状态跟踪）

### 当前进度
- 数据接入能力基础架构已搭建
- 调度器可正常运行
- 自动同步作业已实现（待进一步测试）

---

## 后续任务概览

| 阶段 | 任务 | 预计工时 | 优先级 |
|------|------|----------|--------|
| **阶段 1** | 同步状态服务 | 2-3h | 高 |
| **阶段 1** | 完善定时任务（重试、超时） | 2-3h | 高 |
| **阶段 1** | API 接口（4 个端点） | 3-4h | 高 |
| **阶段 1** | 集成测试 | 2-3h | 高 |
| **阶段 2** | WebSocket 实时数据推送 | 8-12h | 中 |
| **阶段 2** | 回补断点智能检测 | 4-6h | 中 |
| **阶段 3** | 回测引擎基础 | 12-16h | 中 |
| **阶段 3** | 前端 UI 基础框架 | 8-12h | 低 |

---

## 阶段 1: 数据接入能力完善（核心功能）

### 任务 1: 同步状态服务

#### 目标
创建 `SyncStateService` 类，封装所有与同步状态相关的数据库操作。

#### 技术方案

**文件位置**: `app/services/sync_state_service.py`

**核心功能**:

```python
class SyncStateService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # 查询方法
    async def get_by_market_timeframe(self, market_id: int, timeframe: str) -> Optional[DataSyncState]
    async def list_auto_syncing(self, status: Optional[str] = None) -> list[DataSyncState]
    async def list_by_exchange(self, exchange: str) -> list[DataSyncState]
    async def get_error_states(self) -> list[DataSyncState]

    # 创建/更新方法
    async def get_or_create(self, market_id: int, timeframe: str, **kwargs) -> DataSyncState
    async def update_sync_time(self, market_id: int, timeframe: str, sync_time: datetime) -> DataSyncState
    async def set_status(self, market_id: int, timeframe: str, status: str, error: Optional[str] = None) -> DataSyncState
    async def enable_auto_sync(self, market_id: int, timeframe: str) -> DataSyncState
    async def disable_auto_sync(self, market_id: int, timeframe: str) -> DataSyncState

    # 批量操作
    async def enable_auto_sync_batch(self, market_ids: list[int], timeframes: list[str]) -> int
    async def reset_error_states(self) -> int
```

**关键设计点**:
- 使用 `selectinload` 预加载 `market` 关系
- 添加缓存层（Redis）减少数据库查询
- 批量操作使用 bulk update

#### 实施步骤
1. 创建 `SyncStateService` 类
2. 实现基础查询方法
3. 实现状态管理方法
4. 实现批量操作方法
5. 编写单元测试
6. 更新 `jobs.py` 使用新服务

---

### 任务 2: 完善定时任务

#### 目标
增强定时任务的健壮性，添加错误重试和超时控制。

#### 技术方案

**2.1 错误重试机制**

在调度器配置中添加重试参数：

```python
job_defaults = {
    "coalesce": True,
    "max_instances": 3,
    "misfire_grace_time": 300,
    "max_retries": 3,  # 新增
    "retry_delay": 60,  # 新增：秒
}
```

**2.2 作业超时控制**

使用 `asyncio.timeout` 防止作业长时间阻塞：

```python
async def auto_sync_ohlcv():
    try:
        async with asyncio.timeout(300):  # 5 分钟超时
            # 同步逻辑
    except asyncio.TimeoutError:
        logger.error("Auto-sync job timed out")
        # 标记所有 syncing 状态为 error
```

**2.3 作业健康监控**

添加作业执行统计：

```python
class JobStats:
    total_runs: int
    successful_runs: int
    failed_runs: int
    last_run_time: datetime
    last_error: str
```

存储在 Redis 中，可通过 API 查询。

**2.4 作业依赖关系**

某些作业需要依赖其他作业完成：

```python
# 确保 market sync 完成后再启动 auto sync
scheduler.add_job(
    sync_markets_metadata,
    "cron",
    hour=0,
    minute=0,
    id="sync_markets_metadata",
)

scheduler.add_job(
    auto_sync_ohlcv,
    "interval",
    minutes=1,
    id="auto_sync_ohlcv",
    misfire_grace_time=300,
)
```

#### 实施步骤
1. 更新调度器配置
2. 添加超时控制装饰器
3. 实现 JobStats 统计
4. 添加作业健康检查 API
5. 编写重试和超时测试

---

### 任务 3: API 接口

#### 目标
创建 4 个新的 API 端点，用于管理和监控同步状态。

#### 技术方案

**3.1 GET /api/v1/data/sync_state**

查询同步状态列表

**查询参数**:
- `market_id`: 过滤市场
- `timeframe`: 过滤周期
- `sync_status`: 过滤状态 (idle, syncing, error)
- `exchange`: 过滤交易所
- `has_errors`: 仅返回有错误的
- `limit`: 分页大小（默认 100）
- `offset`: 分页偏移

**响应**:
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
      "last_error_time": null,
      "created_at": "2026-03-01T00:00:00Z",
      "updated_at": "2026-03-03T10:05:00Z"
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0
}
```

**3.2 POST /api/v1/data/backfill**

手动触发历史数据回补

**请求体**:
```json
{
  "market_ids": [1, 2, 3],  // 可选
  "timeframes": ["1h", "4h", "1d"],
  "start_time": "2026-01-01T00:00:00Z",
  "end_time": "2026-03-01T00:00:00Z",
  "symbol_pattern": "BTC/*",  // 可选：匹配模式
  "force": false  // 是否强制覆盖已有数据
}
```

**响应**:
```json
{
  "task_id": "backfill_20260303_100000",
  "status": "queued",
  "estimated_markets": 10,
  "estimated_timeframes": 30,
  "message": "Backfill task queued for 30 combinations"
}
```

**实现要点**:
- 使用 Celery 或后台任务处理（对于大任务）
- 小任务直接在请求中处理
- 任务状态存储在 Redis
- 提供 `GET /api/v1/data/backfill/{task_id}` 查询进度

**3.3 POST /api/v1/data/auto_sync**

启动/停止自动同步

**请求体**:
```json
{
  "market_id": 1,
  "timeframes": ["1h", "4h", "1d"],
  "enabled": true
}
```

**响应**:
```json
{
  "updated": 3,
  "message": "Auto-sync enabled for 3 timeframes"
}
```

**3.4 GET /api/v1/scheduler/status**

查询调度器状态

**响应**:
```json
{
  "running": true,
  "job_store": "redis",  // 或 "memory"
  "jobs": [
    {
      "id": "auto_sync_ohlcv",
      "name": "Auto Sync OHLCV",
      "next_run_time": "2026-03-03T10:01:00Z",
      "last_run_time": "2026-03-03T10:00:00Z",
      "stats": {
        "total_runs": 1440,
        "successful_runs": 1435,
        "failed_runs": 5,
        "last_error": null
      }
    }
  ],
  "active_connections": 2
}
```

#### 实施步骤
1. 创建 API 路由文件 `app/api/v1/sync.py`
2. 实现查询端点（带过滤和分页）
3. 实现回补端点（后台任务）
4. 实现自动同步控制端点
5. 实现调度器状态端点
6. 编写 API 集成测试

---

### 任务 4: 集成测试

#### 目标
编写端到端测试，验证完整功能流程。

#### 测试场景

**4.1 完整同步流程**

```
1. 启动应用和调度器
2. 同步市场元数据
3. 创建同步状态并启用自动同步
4. 等待调度器执行
5. 验证数据已同步
6. 验证状态已更新
7. 禁用自动同步
8. 清理测试数据
```

**4.2 错误恢复场景**

```
1. 创建无效市场 ID 的同步状态
2. 启用自动同步
3. 等待调度器执行
4. 验证错误被记录
5. 修正市场 ID
6. 验证下次执行成功
```

**4.3 并发控制验证**

```
1. 创建 10 个自动同步状态
2. 配置 MAX_CONCURRENT_SYNCS=3
3. 同时触发同步
4. 验证最多 3 个并发
5. 验证所有任务最终完成
```

**4.4 API 接口测试**

- 测试所有新端点的各种参数组合
- 测试错误情况（无效参数、权限等）
- 测试分页和过滤

#### 实施步骤
1. 编写测试用例
2. 使用 pytest-asyncio 运行测试
3. 使用测试数据库和 Redis
4. 添加覆盖率报告
5. CI/CD 集成

---

## 阶段 2: 数据接入增强（优化功能）

### 任务 5: WebSocket 实时数据推送

#### 目标
通过 WebSocket 推送实时 OHLCV 数据更新，支持前端实时显示。

#### 技术方案

**5.1 WebSocket 端点**

```
WS /ws/data/ohlcv?market_id=1&timeframe=1h
```

**消息格式**:
```json
{
  "type": "ohlcv_update",
  "market_id": 1,
  "timeframe": "1h",
  "data": [
    1700000000000,  // timestamp_ms
    50000.0,        // open
    51000.0,        // high
    49500.0,        // low
    50800.0,        // close
    1000.0          // volume
  ]
}
```

**5.2 订阅管理**

- 支持多市场订阅
- 心跳检测
- 自动重连

**5.3 数据源**

两种方案：
- 方案 A: 调用交易所 WebSocket API（实时性好）
- 方案 B: 定时轮询 + 推送（实现简单）

建议先用方案 B，后续升级为方案 A。

#### 实施步骤
1. 实现 WebSocket 连接管理器
2. 实现数据推送逻辑
3. 添加订阅/取消订阅功能
4. 编写客户端测试
5. 文档和使用示例

---

### 任务 6: 回补断点智能检测

#### 目标
自动检测数据缺口并触发回补，无需手动配置。

#### 技术方案

**6.1 缺口检测算法**

```python
async def detect_gaps(market_id: int, timeframe: str):
    # 获取最新 1000 条数据
    candles = await get_recent_candles(market_id, timeframe, 1000)

    # 检查时间间隔
    expected_interval = timeframe_to_seconds(timeframe)
    gaps = []

    for i in range(len(candles) - 1):
        actual_interval = (candles[i+1].time - candles[i].time).total_seconds()
        if actual_interval > expected_interval * 1.1:  # 允许 10% 误差
            gaps.append({
                "start": candles[i].time,
                "end": candles[i+1].time,
                "missing_candles": int(actual_interval / expected_interval) - 1
            })

    return gaps
```

**6.2 智能回补策略**

- 根据缺口大小决定回补方式
- 小缺口（< 10 条）：直接补齐
- 中缺口（10-100 条）：创建后台任务
- 大缺口（> 100 条）：通知管理员，等待手动确认

**6.3 优先级管理**

```python
GAP_PRIORITY = {
    "small": 1,   # 1-10 条缺失，高优先级
    "medium": 2,  # 11-100 条缺失，中优先级
    "large": 3,   # >100 条缺失，低优先级
}
```

#### 实施步骤
1. 实现缺口检测算法
2. 创建缺口表记录检测到的缺口
3. 实现智能回补逻辑
4. 添加优先级队列
5. 添加监控面板

---

## 阶段 3: 交易能力构建（核心业务）

### 任务 7: 回测引擎基础

#### 目标
构建基础回测引擎，验证策略历史表现。

#### 技术方案

**7.1 回测引擎架构**

```
BacktestEngine
├── DataProvider: 数据接口
├── ExchangeSim: 交易所模拟
├── Strategy: 策略基类
├── Performance: 性能指标
└── Results: 回测结果
```

**7.2 核心组件**

```python
class BacktestEngine:
    def __init__(self, start_date: datetime, end_date: datetime, initial_capital: float):
        self.data_provider = DataProvider()
        self.exchange = ExchangeSim(initial_capital)
        self.strategy = None

    async def run(self, strategy: Strategy) -> BacktestResult:
        self.strategy = strategy
        for data in self.data_provider.iterate():
            signal = self.strategy.generate_signal(data)
            if signal:
                await self.execute_order(signal)
        return self.calculate_results()
```

**7.3 性能指标**

- 总收益率
- 年化收益率
- 最大回撤
- 夏普比率
- 胜率
- 盈亏比

#### 实施步骤
1. 设计回测引擎架构
2. 实现数据提供者
3. 实现交易所模拟
4. 实现策略基类
5. 实现性能指标计算
6. 编写示例策略和测试

---

### 任务 8: 前端 UI 基础框架

#### 目标
搭建前端基础框架，提供数据可视化和基本管理界面。

#### 技术方案

**8.1 技术栈**

- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- ShadcnUI 组件库
- Recharts (图表)
- TanStack Query (数据获取)

**8.2 页面规划**

```
/
├── Dashboard          # 仪表盘
├── Markets            # 市场列表
├── Sync               # 同步管理
├── Data               # 数据查询
├── Backtest           # 回测（阶段 3）
└── Settings           # 设置
```

**8.3 核心功能**

1. **仪表盘**
   - 同步状态概览
   - 最近错误
   - 数据覆盖范围
   - 实时数据图表

2. **市场管理**
   - 市场列表（搜索、过滤）
   - 查看市场详情
   - 配置同步参数

3. **同步管理**
   - 启用/禁用自动同步
   - 查看同步状态
   - 查看错误日志
   - 手动触发回补

4. **数据查询**
   - OHLCV 图表
   - 数据导出
   - 高级查询

#### 实施步骤
1. 初始化 Next.js 项目
2. 配置 Tailwind 和 ShadcnUI
3. 设计页面布局
4. 实现数据获取
5. 实现图表组件
6. 实现交互功能

---

## 阶段 4: 运维和监控

### 任务 9: 监控和告警

#### 目标
建立完善的监控体系，及时发现和处理问题。

#### 监控指标

**9.1 应用指标**
- API 响应时间
- 错误率
- 请求量
- 内存和 CPU 使用

**9.2 数据同步指标**
- 同步成功率
- 平均同步延迟
- 缺口数量
- API 调用次数

**9.3 数据库指标**
- 连接池使用率
- 查询慢查询
- 表大小增长

#### 告警规则

- 同步失败率 > 10% (5 分钟内)
- API 响应时间 > 5s (P95)
- 数据缺口 > 100 条
- 内存使用 > 80%

#### 技术方案

- Prometheus + Grafana
- 或使用云服务（如 Datadog）
- 告警通过 Slack/邮件发送

---

## 任务优先级总结

### P0 (必须完成 - 核心功能)
1. 同步状态服务
2. 完善定时任务
3. API 接口
4. 集成测试

### P1 (重要功能 - 优化体验)
5. WebSocket 实时数据推送
6. 回补断点智能检测

### P2 (核心业务 - 交易能力)
7. 回测引擎基础

### P3 (用户界面 - 可视化)
8. 前端 UI 基础框架

### P4 (运维保障 - 稳定性)
9. 监控和告警

---

## 时间线建议

| 周次 | 阶段 | 任务 |
|------|------|------|
| Week 1 | 阶段 1 | 任务 1-4 (数据接入完善) |
| Week 2 | 阶段 2 | 任务 5 (WebSocket 推送) |
| Week 3 | 阶段 2 | 任务 6 (回补检测) |
| Week 4-5 | 阶段 3 | 任务 7 (回测引擎) |
| Week 6-7 | 阶段 3 | 任务 8 (前端 UI) |
| Week 8 | 阶段 4 | 任务 9 (监控告警) |

---

## 技术债务清单

| 项目 | 影响 | 计划处理时间 |
|------|------|--------------|
| Redis 恢复后不自动切换 | 低 | Week 2 |
| 缺少单元测试覆盖率 | 中 | Week 1 |
| API 缺少认证和权限 | 高 | Week 3 |
| 日志格式不统一 | 低 | Week 2 |
| 配置管理分散 | 中 | Week 1 |

---

## 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 交易所 API 限流 | 高 | 高 | 并发控制、速率限制 |
| 数据量过大导致性能问题 | 中 | 高 | 分区、归档、缓存 |
| Redis 单点故障 | 低 | 中 | 主从复制、哨兵 |
| 调度器任务积压 | 中 | 中 | 监控告警、动态扩容 |

---

## 备注

- 本计划可根据实际需求调整优先级
- 建议先完成阶段 1，确保核心功能稳定
- 前端开发可并行进行，后端提供 API 即可
- 回测引擎是可选的高级功能，可根据业务需求决定优先级