# 调度器系统设计 (Scheduler System Design)

本文档介绍 Kurisu 后端调度器系统的设计与实现，覆盖生命周期、任务模型、并发控制、容错策略、可观测性与扩展方式。

## 1. 设计目标

- 在应用进程内稳定执行周期性后台任务（市场同步、OHLCV 自动同步、缺口检测）
- 控制与交易所交互并发，降低触发限流与网络抖动导致失败的概率
- 通过 Redis 持久化调度元信息与任务统计，支持运行时观测
- 在 Redis 不可用时回退内存模式，确保核心任务仍可运行
- 将任务逻辑与调度框架解耦，便于迭代与测试

## 2. 架构总览

调度器采用 APScheduler + AsyncIO 方案，主流程如下：

1. FastAPI 启动时根据配置决定是否启动调度器
2. 调度器初始化 jobstore（优先 Redis，失败回退内存）
3. 注册默认任务（3 个）并进入周期调度
4. 任务执行过程中写入 Redis 统计信息
5. FastAPI 关闭时先关闭交易所连接，再停止调度器

核心模块：

- `backend/app/scheduler/scheduler.py`：调度器生命周期、任务注册、对外查询接口
- `backend/app/scheduler/jobs.py`：任务实现、并发控制、重试与统计
- `backend/app/scheduler/state.py`：同步状态读写辅助函数（兼容路径）
- `backend/app/api/v1/sync.py`：调度器状态查询与数据同步/回填 API

## 3. 启停与生命周期

### 3.1 启动流程

应用生命周期在 `backend/app/main.py` 中定义：

- 完成数据库与 Redis 健康检查
- 当 `SCHEDULER_ENABLED=true` 时调用 `start_scheduler()`
- 调度器内部执行：
  - 构建 `AsyncIOScheduler`
  - 配置 `AsyncIOExecutor`
  - 设置作业默认参数（`coalesce=True`, `max_instances=3`, `misfire_grace_time=300`）
  - 注册默认任务
  - 启动调度器

### 3.2 Job Store 策略

调度器优先使用 Redis JobStore：

- 优点：重启后任务定义可恢复
- 检测方式：初始化时主动 `ping` Redis
- 失败回退：切换到 `MemoryJobStore`

回退语义：

- 内存模式下应用重启后任务定义会丢失
- 但当前进程内调度能力仍保留，避免“因 Redis 短暂异常导致调度系统不可用”

### 3.3 关闭流程

关闭顺序：

1. 调用 `close_exchange_services()` 释放交易所连接
2. `shutdown_scheduler(wait=True)` 等待在途任务安全退出
3. 清空全局 scheduler 引用

该顺序可避免调度器仍在拉取数据时底层连接被提前释放。

## 4. 默认任务设计

系统注册 3 个默认任务：

### 4.1 auto_sync_ohlcv

- 触发器：`interval`
- 周期：`AUTO_SYNC_INTERVAL_MINUTES`
- 作用：为开启自动同步的市场/周期拉取最新 OHLCV 数据

执行关键点：

1. 查询空闲（`idle`）同步状态
2. 并发执行市场级同步（受信号量限制）
3. 成功后更新 `last_sync_time`（以数据库最后一根 K 线时间为准）
4. 失败状态写入 `error`

### 4.2 sync_markets_metadata

- 触发器：`cron`
- 周期：每日 `MARKET_SYNC_HOUR:00`
- 作用：同步交易所市场元信息（交易对、精度等）

执行关键点：

1. 遍历配置项 `EXCHANGES`
2. 复用缓存后的 `ExchangeService`
3. 当前实现默认仅同步 `USDT` 交易对

### 4.3 check_backfill_gaps

- 触发器：`interval`
- 周期：`BACKFILL_CHECK_INTERVAL_HOURS`
- 作用：检测 OHLCV 最近窗口缺口并尝试自动回填

执行关键点：

1. 对自动同步状态扫描最近 100 根 K 线
2. 根据 timeframe 推导期望间隔（允许 10% 容差）
3. 缺口分级处理：
  - `<= 50` 根缺失：自动回填
  - `> 50` 根缺失：仅记录告警，建议人工回填

## 5. 并发模型与资源管理

### 5.1 API 并发控制

`jobs.py` 使用：

- 全局信号量 `_sync_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SYNCS)`
- 控制单次调度周期内并发的市场同步数量

这样可在吞吐和限流风险间平衡。

### 5.2 交易所连接复用

- `_exchange_services` 缓存 `exchange_id -> ExchangeService`
- `_exchange_lock` 保证缓存创建与访问线程安全
- 任务复用同一连接，降低重复建连开销

### 5.3 数据库会话

- 每个调度任务使用 `SessionLocal()` 独立会话
- 批量处理后统一 `commit`
- 与 API 请求会话隔离，减少相互影响

## 6. 容错与稳定性策略

### 6.1 超时控制

三类任务都包裹 `asyncio.timeout(JOB_TIMEOUT)`，默认 300 秒。

目的：

- 防止外部依赖阻塞导致任务长时间挂起
- 快速释放调度槽位，避免任务堆积

### 6.2 重试策略

OHLCV 抓取采用 `_fetch_with_retry()`：

- 最大重试：2 次（总尝试 3 次）
- 退避：指数退避 `2^attempt` 秒
- 对瞬态错误（网络抖动、临时限流）有较好恢复能力

### 6.3 失败状态传播

- 单市场同步失败会将同步状态标记为 `error`
- 任务级异常会写入 job stats 的 `last_error`
- 降低“静默失败”风险，便于定位问题

## 7. 观测与运维接口

### 7.1 Job 统计

任务统计保存在 Redis，key 格式：

- `job_stats:auto_sync_ohlcv`
- `job_stats:sync_markets_metadata`
- `job_stats:check_backfill_gaps`

字段包括：

- `total_runs`, `successful_runs`, `failed_runs`
- `total_synced`, `total_failed`, `total_gaps`
- `last_run_time`, `last_error`

TTL 为 24 小时（`setex 86400`）。

### 7.2 状态查询 API

`GET /api/v1/scheduler/status` 返回：

- 调度器是否运行
- 当前 jobstore 类型（redis/memory）
- 每个任务下次运行时间与最近统计
- 当前活跃交易所连接数

### 7.3 回填任务监控

回填 API 将任务状态写入 Redis：

- `backfill_task:{task_id}`
- 支持 `pending/running/completed/failed`
- 可通过 `GET /api/v1/data/backfill/{task_id}` 查询

## 8. 配置项说明

配置位于 `backend/app/core/config.py`：

- `SCHEDULER_ENABLED`：是否启用调度器
- `AUTO_SYNC_INTERVAL_MINUTES`：自动同步任务间隔
- `MARKET_SYNC_HOUR`：市场元数据同步小时（UTC）
- `BACKFILL_CHECK_INTERVAL_HOURS`：缺口检测间隔
- `MAX_CONCURRENT_SYNCS`：最大并发同步数
- `EXCHANGES`：需要同步的交易所列表

建议：

- 小规模部署可先维持默认值
- 大规模市场集合下优先提升 `AUTO_SYNC_INTERVAL_MINUTES`，再谨慎提升 `MAX_CONCURRENT_SYNCS`
- 若出现交易所限流，优先下调并发并拉长周期

## 9. 设计取舍与已知边界

### 9.1 主要取舍

- 选择应用内调度而非独立任务队列系统，降低系统复杂度
- 通过“Redis 优先 + 内存回退”平衡可靠性与可用性
- 缺口回填对大缺口默认保守处理，避免自动任务造成过大外部负载

### 9.2 当前边界

- 任务统计 TTL 仅 24 小时，不适合长期趋势分析
- 大缺口（>50）默认不自动修复，需要人工触发回填
- 当前市场元数据同步任务对交易对有默认筛选（USDT）

## 10. 扩展指南

新增一个周期任务建议步骤：

1. 在 `backend/app/scheduler/jobs.py` 增加 `async def` 任务函数
2. 统一加上超时、异常捕获和 `_update_job_stats()`
3. 如涉及外部 API，复用现有并发控制与连接缓存机制
4. 在 `backend/app/scheduler/scheduler.py` 的 `_register_default_jobs()` 注册任务
5. 在 `GET /api/v1/scheduler/status` 响应中确认可观测字段是否完整
6. 补充 `backend/tests` 下对应测试（成功路径、异常路径、边界数据）

## 11. 调优建议（生产环境）

- 以“任务执行耗时分位数”反推调度周期，避免任务重叠
- 对高频任务建立失败告警阈值（如连续失败次数）
- 为不同交易所分配独立并发预算（未来可演进）
- 将 job stats 同步到长期时序存储，用于容量评估和回归分析

---

关联文档：

- [项目现状报告](../project-status.md)
- [数据库模式设计](database-schema-design-zh.md)
- [Redis 调研](redis-research-zh.md)