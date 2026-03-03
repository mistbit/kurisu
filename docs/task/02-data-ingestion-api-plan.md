# 数据接入与 API 开发计划

在完成数据库层重构后，接下来的重点是实现数据的自动化接入（Data Ingestion）以及为前端和策略层提供数据访问的 API 接口。

## 1. 数据接入层 (Data Ingestion)

目标：构建稳定、高效的数据获取管道，支持实时和历史数据的抓取。

### 1.1 架构设计
- **核心组件**:
  - `MarketService`: 负责市场元数据（交易对）的同步。
  - `MarketDataService`: 负责 K 线（OHLCV）和成交（Trades）数据的抓取。
  - `ExchangeInterface`: 基于 CCXT 的统一交易所适配层。
- **技术选型**:
  - `ccxt.async_support`: 异步交易所 API 客户端。
  - `asyncio`: 并发任务管理。
  - `apscheduler`: 定时任务调度（可选，或使用简单的 `while True` 循环配合 `asyncio.sleep`）。

### 1.2 详细任务分解

#### 1.2.1 市场元数据同步
- [x] **实现 `ExchangeService`**:
  - 封装 CCXT 客户端，处理连接、鉴权、错误重试。
  - 实现 `fetch_markets()` 方法。
- [x] **实现 `sync_markets` 任务**:
  - 从交易所获取最新交易对信息。
  - 更新数据库中的 `markets` 表（新增/更新）。
  - 支持黑白名单过滤（如仅同步 `USDT` 交易对）。

#### 1.2.2 历史数据回补 (Backfill)
- [x] **实现 `fetch_ohlcv_history`**:
  - 支持指定时间范围、周期（timeframe）。
  - 处理分页/分批次抓取（CCXT 的 `since` 参数）。
  - 处理 API 速率限制（Rate Limiting）。
- [x] **实现数据入库**:
  - 批量插入（`bulk_insert`）到 TimescaleDB Hypertable。
  - 处理主键冲突（`ON CONFLICT DO NOTHING` 或 `UPDATE`）。

#### 1.2.3 实时数据抓取 (Real-time)
- [ ] **WebSocket 接入 (进阶)**:
  - 优先使用 CCXT Pro (如果可用) 或交易所原生 WebSocket API。
  - 实现 `OrderBook` 和 `Trade` 流的订阅。
- [ ] **轮询机制 (基础)**:
  - 对于不支持 WebSocket 的场景，实现高效的 REST API 轮询。
  - 动态调整轮询间隔，避免触发限流。

### 1.3 数据一致性与幂等策略
- [x] **唯一键与冲突策略**:
  - `markets` 使用 `(exchange, symbol)` 唯一键。
  - `ohlcv` 使用 `(time, market_id, timeframe)` 唯一键。
  - `trades` 使用 `(time, market_id, trade_id)` 唯一键。
- [x] **时间与精度规范**:
  - 全链路统一使用 UTC。
  - CCXT 毫秒时间戳转换为数据库时区感知时间。
- [ ] **回补断点**:
  - 记录每个 `market_id + timeframe` 的 last_sync_time，避免全量重跑。

## 2. API 接口层 (REST API)

目标：提供清晰、规范的 HTTP 接口，供前端仪表盘和策略引擎使用。

### 2.1 架构设计
- **框架**: FastAPI
- **规范**: OpenAPI (Swagger UI)
- **数据交互**: Pydantic Models (Schemas) <-> SQLAlchemy Models

### 2.2 详细任务分解

#### 2.2.1 基础配置
- [ ] **API 路由规划**:
  - `/api/v1/markets`: 市场相关
  - `/api/v1/data`: 历史数据查询
- [ ] **依赖注入**:
  - 封装 `get_db` 依赖。
  - 封装 `get_exchange_service` 依赖。

#### 2.2.2 市场接口 (`/markets`)
- [ ] `GET /markets`: 获取所有支持的交易对列表（支持分页、过滤）。
- [ ] `GET /markets/{id}`: 获取特定交易对详情。
- [ ] `POST /markets/sync`: 手动触发市场元数据同步（管理端功能）。

#### 2.2.3 数据接口 (`/data`)
- [ ] `GET /data/ohlcv`: 查询 K 线数据。
  - 参数: `market_id`, `timeframe`, `start_time`, `end_time`, `limit`。
  - 响应: JSON 数组，包含 `[timestamp, open, high, low, close, volume]`。
- [ ] `GET /data/trades`: 查询近期成交数据（可选）。

### 2.3 接口约束与可观测性
- [ ] **响应排序与上限**:
  - 支持 `order=asc/desc`，限制 `limit` 最大值。
- [ ] **基础诊断接口**:
  - `GET /api/v1/health`
  - `GET /api/v1/version`

## 3. 实施路线图

1.  **第一阶段：基础数据管道**
    - 完成 `ExchangeService` 封装。
    - 实现 `sync_markets` 并验证入库。
    - 实现基础的 `fetch_ohlcv_history`。

2.  **第二阶段：API 基础**
    - 搭建 FastAPI 路由结构。
    - 实现 `/markets` 和 `/data/ohlcv` 接口。
    - 联调：通过 API 查询第一阶段抓取的数据。

3.  **第三阶段：实时性与优化**
    - 引入定时任务调度器。
    - 优化数据插入性能。
    - 完善错误处理与日志记录。

## 4. 下一步行动

建议先创建任务文件 `docs/task/02-data-ingestion-api-plan.md` (即本文档)，然后按照 **第一阶段：基础数据管道** 开始编码。
