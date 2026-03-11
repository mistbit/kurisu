# Kurisu 工程现状总结报告

> 生成日期：2026-03-11  
> 代码统计：后端应用 5,993 行 | 测试 2,046 行 | 前端 3,469 行 | 数据库迁移 523 行  
> 测试状态：70 passed, 1 failed, 1 skipped

---

## 目录

- [一、项目概述](#一项目概述)
- [二、整体完成度](#二整体完成度)
- [三、后端详细分析](#三后端详细分析)
  - [3.1 核心基础设施](#31-核心基础设施)
  - [3.2 API 端点](#32-api-端点)
  - [3.3 业务服务层](#33-业务服务层)
  - [3.4 数据库模型](#34-数据库模型)
  - [3.5 调度器系统](#35-调度器系统)
  - [3.6 策略与回测引擎](#36-策略与回测引擎)
  - [3.7 WebSocket 实时推送](#37-websocket-实时推送)
- [四、前端详细分析](#四前端详细分析)
- [五、测试现状](#五测试现状)
- [六、代码质量分析](#六代码质量分析)
- [七、存在的问题与风险](#七存在的问题与风险)
- [八、各阶段完成度总览](#八各阶段完成度总览)
- [九、建议优先处理事项](#九建议优先处理事项)

---

## 一、项目概述

**Kurisu** 是一个 AI-Native 量化交易代理研究平台，采用微服务就绪的单体架构，桥接量化金融与现代 AI Agent（LangGraph）。项目包含模块化策略引擎、认知 AI 代理和现代仪表盘。

**技术栈：**
- 后端：FastAPI + async SQLAlchemy + PostgreSQL/TimescaleDB + Redis
- 前端：Next.js 16.1.6 + TypeScript + Tailwind CSS 4 + ShadcnUI
- 交易所集成：CCXT（async_support）
- AI 框架：LangChain / LangGraph（尚未实现）
- 测试：pytest + httpx AsyncClient
- 代码检查：ruff

---

## 二、整体完成度

| 阶段 | 名称 | 状态 | 完成度 |
|------|------|------|--------|
| Phase 1 | 基础设施 | ✅ 已完成 | 100% |
| Phase 2 | 量化引擎 | 🔄 进行中 | ~75% |
| Phase 2.5 | 安全与鉴权 | ✅ 已完成 | 100% |
| Phase 3 | AI Agent 集成 | ❌ 未开始 | 0% |
| Phase 4 | 实盘交易与风控 | ❌ 未开始 | 0% |
| 前端仪表盘 | Dashboard UI | 🔄 进行中 | ~60% |

---

## 三、后端详细分析

### 3.1 核心基础设施

| 组件 | 文件 | 行数 | 状态 | 说明 |
|------|------|------|------|------|
| FastAPI 应用 | `app/main.py` | 253 | ✅ 完成 | 应用初始化、生命周期管理、健康检查、市场 API |
| 配置管理 | `app/core/config.py` | ~80 | ✅ 完成 | Pydantic Settings，支持 .env，计算字段生成 DATABASE_URL / REDIS_URL |
| 数据库连接 | `app/core/database.py` | ~60 | ✅ 完成 | async SQLAlchemy 引擎，连接池配置，会话工厂 |
| Redis 客户端 | `app/core/redis.py` | ~30 | ✅ 完成 | async Redis 客户端，支持超时配置 |
| 鉴权依赖 | `app/core/deps.py` | 223 | ✅ 完成 | JWT / API Key 双模式鉴权，速率限制，超级用户权限 |

### 3.2 API 端点

#### 认证模块 (`/api/v1/auth/`) — 297 行 ✅ 完成

| 端点 | 方法 | 说明 |
|------|------|------|
| `/auth/register` | POST | 用户注册（邮箱验证、重复检查） |
| `/auth/login` | POST | JWT 登录（默认 30 分钟过期） |
| `/auth/me` | GET | 获取当前用户信息（含速率限制） |
| `/auth/password` | POST | 修改密码（需验证旧密码） |
| `/auth/api-keys` | POST | 创建 API Key |
| `/auth/api-keys` | GET | 列出用户的 API Key |
| `/auth/api-keys/{id}` | DELETE | 撤销 API Key |
| `/admin/users` | GET | 列出所有用户（超级用户） |
| `/admin/users/{id}` | DELETE | 停用用户账户（超级用户） |

#### 市场数据模块 (`main.py` 内) ✅ 完成

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/markets` | GET | 市场列表查询，支持交易所/symbol/状态过滤与分页 |
| `/api/v1/markets/{market_id}` | GET | 获取单个市场详情 |
| `/api/v1/markets/sync` | POST | 触发交易所市场元数据同步 |

#### 数据同步模块 (`/api/v1/data/`) — 482 行 ✅ 完成

| 端点 | 方法 | 说明 |
|------|------|------|
| `/data/ohlcv` | GET | OHLCV 数据查询（按 market_id、timeframe、时间范围）|
| `/data/sync_state` | GET | 同步状态列表（支持多维过滤与分页） |
| `/data/sync_state/{id}` | GET | 获取单个同步状态 |
| `/data/backfill` | POST | 触发后台回填任务（返回 task_id） |
| `/data/backfill/{task_id}` | GET | 查询回填任务进度 |
| `/data/auto_sync` | POST | 启用/禁用市场自动同步 |

#### 调度器模块 (`/api/v1/scheduler/`) ✅ 完成

| 端点 | 方法 | 说明 |
|------|------|------|
| `/scheduler/status` | GET | 调度器状态与任务统计 |

#### 回测模块 (`/api/v1/backtest/`) — 158 行 ✅ 完成

| 端点 | 方法 | 说明 |
|------|------|------|
| `/backtest/run` | POST | 执行回测（支持策略参数配置） |
| `/backtest/strategies` | GET | 获取可用策略列表 |

#### WebSocket (`/ws/`) — 307 行 ✅ 完成

| 端点 | 说明 |
|------|------|
| `/ws/data/ohlcv?market_id={id}&timeframe={tf}` | OHLCV 实时数据流推送 |

#### 通用端点 ✅ 完成

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查（DB + Redis） |
| `/api/v1/health` | GET | v1 版本健康检查 |
| `/api/v1/version` | GET | 应用版本号 |

### 3.3 业务服务层

| 服务 | 文件 | 行数 | 状态 | 说明 |
|------|------|------|------|------|
| ExchangeService | `services/exchange.py` | 197 | ✅ 完成 | CCXT 封装：初始化/关闭生命周期、行情获取、OHLCV 拉取 |
| MarketService | `services/exchange.py` | (同上) | ✅ 完成 | 市场元数据同步，支持白名单/黑名单过滤，upsert 逻辑 |
| MarketDataService | `services/exchange.py` | (同上) | ✅ 完成 | 历史 OHLCV 数据分页拉取、批量 upsert |
| SyncStateService | `services/sync_state_service.py` | 480 | ✅ 完成 | 同步状态管理，Redis 缓存，上下文管理器，批量操作 |
| UserService | `services/user_service.py` | 220 | ✅ 完成 | 用户 & API Key CRUD 操作 |
| AuthService | `services/auth.py` | 108 | ✅ 完成 | JWT 签发/验证、密码哈希、API Key 生成 |
| RateLimiter | `services/rate_limiter.py` | 117 | ✅ 完成 | Redis 滑动窗口速率限制 |
| OHLCVStreamService | `services/ohlcv_stream.py` | 226 | ✅ 完成 | WebSocket 轮询推送，交易所连接复用，数据库存储 |

### 3.4 数据库模型

| 模型 | 所属文件 | 说明 | 状态 |
|------|----------|------|------|
| Market | `models/market.py` | 交易对（交易所、symbol、精度、活跃状态） | ✅ |
| OHLCV | `models/market.py` | K 线数据（TimescaleDB 超表，复合主键） | ✅ |
| Trade | `models/market.py` | 逐笔交易记录 | ✅ |
| User | `models/account.py` | 用户（用户名、邮箱、密码哈希） | ✅ |
| APIKey | `models/account.py` | API 密钥（哈希存储、速率限制、过期时间） | ✅ |
| Account | `models/account.py` | 交易账户 | ✅ |
| Balance | `models/account.py` | 资产余额（时序） | ✅ |
| Position | `models/order.py` | 持仓记录（含未实现盈亏） | ✅ |
| Order | `models/order.py` | 订单记录（含状态跟踪） | ✅ |
| Execution | `models/order.py` | 成交明细 | ✅ |
| Strategy | `models/strategy.py` | 策略定义（类路径、参数） | ✅ |
| StrategyRun | `models/strategy.py` | 策略运行记录（含性能指标） | ✅ |
| RiskEvent | `models/strategy.py` | 风控事件日志 | ✅ |
| DataSyncState | `models/sync_state.py` | 数据同步状态跟踪 | ✅ |

**数据库迁移（Alembic）：** 4 个版本文件，涵盖初始 Schema、同步状态表、用户/API Key 表、同步状态增强。

### 3.5 调度器系统

| 组件 | 文件 | 行数 | 状态 |
|------|------|------|------|
| 调度器核心 | `scheduler/scheduler.py` | 233 | ✅ 完成 |
| 定时任务 | `scheduler/jobs.py` | 641 | ✅ 完成 |
| 状态工具 | `scheduler/state.py` | 231 | ✅ 完成 |

**已实现的定时任务：**

| 任务 | 调度间隔 | 说明 |
|------|----------|------|
| `auto_sync_ohlcv` | 每 N 分钟（可配） | 拉取自动同步市场的最新 OHLCV，信号量并发控制 |
| `sync_markets_metadata` | 每日指定时刻 | 同步交易所市场元数据（交易对、精度） |
| `check_backfill_gaps` | 每 N 小时（可配） | 检测 OHLCV 数据缺口，自动回填（≤50 根 K 线的缺口） |

**特性：**
- Redis 作业存储（带内存回退）
- 5 分钟任务超时（`asyncio.timeout()`）
- 指数退避重试逻辑
- Redis 统计跟踪（运行次数、成功/失败计数、耗时）
- 交易所连接池缓存与锁管理

### 3.6 策略与回测引擎

| 组件 | 文件 | 行数 | 状态 |
|------|------|------|------|
| 策略基类 | `strategy/base.py` | 230 | ✅ 完成 |
| 交易所模拟器 | `strategy/exchange_sim.py` | 430 | ✅ 完成 |
| 回测引擎 | `strategy/backtest.py` | 458 | ✅ 完成 |
| 示例策略 | `strategy/examples.py` | 215 | ✅ 完成 |

**BaseStrategy 抽象基类：**
- 信号生成接口 (`generate_signal`)
- 历史数据访问 (`get_history`, `get_close_prices`)
- 持仓跟踪 (`has_position`, `get_position`)
- 生命周期钩子 (`init`, `on_bar`, `on_trade`, `on_finish`)

**ExchangeSimulator：**
- 市价单 & 限价单执行
- 滑点和佣金模拟
- 止损/止盈自动触发
- 持仓管理（开仓、部分平仓、全平）

**BacktestEngine：**
- 事件驱动回测，支持日期范围过滤
- 权益曲线跟踪
- 信号处理 → 订单执行 → 交易记录
- 完整的结果计算（返回 BacktestResult）

**PerformanceCalculator：**
- 夏普比率、索提诺比率
- 最大回撤
- 胜率、盈利因子
- 年化收益率

**示例策略：**
- `MovingAverageCrossoverStrategy`：双均线交叉策略，可配置快/慢周期
- `RSIStrategy`：RSI 均值回归策略，可配置超买/超卖阈值

### 3.7 WebSocket 实时推送

**ConnectionManager（307 行）：**
- 多客户端连接管理，基于订阅的消息路由
- 心跳/ping-pong 健康检查（30 秒超时）
- WeakSet 自动清理失效连接
- 连接统计（总连接数、消息发送量）

**OHLCVStreamService（226 行）：**
- 轮询模式拉取交易所最新数据（默认 5 秒间隔）
- 自动广播给订阅客户端
- 数据同步写入数据库
- 交易所连接复用

**注意：** 当前为 HTTP 轮询模式，非交易所原生 WebSocket，存在延迟。

---

## 四、前端详细分析

### 4.1 基础设施 ✅ 完成

| 组件 | 文件 | 说明 |
|------|------|------|
| 布局 | `src/app/layout.tsx` | 根布局，字体加载，全局 Provider |
| 样式 | `src/app/globals.css` | Tailwind CSS 4 + OKLch 色彩空间 + 暗色模式 |
| API 客户端 | `src/lib/api.ts` | Axios 封装，JWT 拦截器，401 自动跳转 |
| 状态管理 | `src/lib/auth-store.ts` | Zustand + persist 持久化 |
| 类型定义 | `src/lib/types.ts` | 完整的 TypeScript 类型（User、Market、OHLCV、BacktestResult 等） |
| 工具函数 | `src/lib/utils.ts` | cn()、防抖、错误提取、日期格式化 |
| 常量 | `src/lib/constants.ts` | 时间框架、交易所列表、策略列表 |
| UI 组件库 | `src/components/ui/` | 20 个 ShadcnUI 组件（Button、Card、Table、Dialog 等） |

### 4.2 页面实现

| 页面 | 路径 | 状态 | 说明 |
|------|------|------|------|
| 首页重定向 | `/` → `/login` | ✅ 完成 | 自动跳转到登录页 |
| 认证布局 | `(auth)/layout.tsx` | ✅ 完成 | 渐变背景、网格装饰、已登录用户自动跳转 |
| 登录页 | `(auth)/login/page.tsx` | ✅ 完成 | 表单、Zustand 存储 token、错误 toast、加载状态 |
| 仪表盘布局 | `(dashboard)/layout.tsx` | ✅ 完成 | 侧边栏导航（Markets/Charts/Backtest）、用户信息、登出、响应式 |
| 市场浏览 | `(dashboard)/markets/page.tsx` | ✅ 完成 | 搜索过滤、交易所筛选、同步按钮、卡片展示、点击跳转 Chart |
| K 线图表 | `(dashboard)/chart/page.tsx` | ✅ 完成 | Recharts OHLC 图表、7 种时间框架、WebSocket 实时更新 |
| 回测界面 | `(dashboard)/backtest/page.tsx` | ⚠️ 部分 | 配置面板完成（策略选择/参数/日期），结果展示部分可能不完整 |

### 4.3 前端缺失部分

| 功能 | 状态 | 说明 |
|------|------|------|
| 注册页面 | ❌ 未实现 | 登录页有链接入口，但 `/register` 页面不存在 |
| 自定义 Hooks | ⚠️ 空目录 | `src/hooks/` 目录存在但无内容 |
| 错误边界 | ❌ 未实现 | 无 React Error Boundary 处理运行时错误 |
| 回测结果可视化 | ⚠️ 可能不完整 | 权益曲线图表、交易列表等展示未确认 |
| 同步状态管理页 | ❌ 未实现 | 后端有完整 API，前端未对接 |
| 调度器监控页 | ❌ 未实现 | 后端有 API，前端未对接 |

---

## 五、测试现状

### 5.1 测试概览

```
运行结果：70 passed, 1 failed, 1 skipped, 2 warnings (11.35s)
```

| 测试文件 | 覆盖范围 | 状态 |
|----------|----------|------|
| `test_health.py` | 健康检查端点 | ✅ 通过 |
| `test_auth.py` | 认证、用户创建、Token、API Key | ✅ 通过 |
| `test_backtest.py` | 回测引擎、策略、交易所模拟器 | ✅ 通过 |
| `test_rate_limiter.py` | 速率限制（禁用/启用/Redis 故障） | ✅ 通过（1 warning） |
| `test_sync_integration.py` | SyncStateService、同步状态操作、批量操作 | ⚠️ 1 失败 |
| `test_gap_detection.py` | 缺口检测算法、缺口场景 | ✅ 通过 |
| `test_websocket.py` | WebSocket 连接管理器、广播 | ✅ 通过 |
| `test_backfill_task.py` | 回填任务执行 | ✅ 通过（1 warning） |
| `test_sync_state.py` | 同步状态 CRUD | ✅ 通过 |

### 5.2 测试基础设施

- 使用 `pytest-asyncio` 支持异步测试
- SQLite 内存数据库用于快速测试
- `AsyncMock` 模拟异步函数
- FastAPI `dependency_overrides` 实现依赖注入
- `conftest.py` 提供统一的 fixture

### 5.3 失败测试详情

**`test_health_check_with_client`** — `test_sync_integration.py:135`

```
assert response.status_code == 200
assert 503 == 200
```

**原因：** 测试环境 Redis 连接失败 (`Event loop is closed`)，健康检查返回 503。属于测试环境 event loop 管理问题，非业务逻辑 bug。

### 5.4 测试缺失

| 缺失测试 | 重要性 | 说明 |
|----------|--------|------|
| 交易所实际连接测试 | 中 | 需要 mock exchange 或 sandbox |
| 端到端 API 流程测试 | 高 | 完整的数据同步 → 回测流程 |
| 调度器任务测试 | 中 | 不含实际调度的任务执行测试 |
| 异常场景覆盖 | 中 | 网络超时、数据异常、并发冲突等边界情况 |
| 前端测试 | 高 | 完全无前端测试 |

---

## 六、代码质量分析

### 6.1 Ruff 检查结果

```
Found 70 errors (51 fixable with --fix)
```

| 错误类型 | 数量 | 说明 |
|----------|------|------|
| `F401` | 51 | 未使用的导入（可自动修复） |
| `F811` | 7 | 变量重定义（测试文件中 `manager` 重定义） |
| `F841` | 8 | 赋值后未使用的局部变量 |
| `E712` | 1 | 避免与 `True` 的相等比较（使用 `if x:` 代替 `if x == True`）|

**评估：** 绝大多数（51/70）是未使用导入的警告，可通过 `ruff check --fix` 一键修复。其余为测试代码中的轻微问题，不影响业务逻辑。

### 6.2 代码优点

- ✅ 全面的 async/await 异步模式
- ✅ 合理的错误处理（try/except 覆盖所有外部调用）
- ✅ 连接池和资源清理
- ✅ 参数化查询防止 SQL 注入
- ✅ 结构化日志（使用 `logging` 模块）
- ✅ 依赖注入设计，便于测试和替换
- ✅ 类型注解覆盖大多数函数
- ✅ 公共方法有 docstring

### 6.3 代码关注点

| 问题 | 严重程度 | 位置 | 说明 |
|------|----------|------|------|
| 速率限制故障开放 | 🟡 中等 | `services/rate_limiter.py` | Redis 故障时默认允许请求通过，存在安全隐患 |
| 缓存失效复杂性 | 🟡 中等 | `services/sync_state_service.py` | 上下文管理器中异常可能导致缓存不一致 |
| WebSocket 轮询模式 | 🟢 低 | `services/ohlcv_stream.py` | HTTP 轮询而非交易所原生 WebSocket，延迟较高 |
| 分页参数验证 | 🟢 低 | `main.py` 市场列表 | `limit` 上限 500，无 `offset` 边界验证 |

---

## 七、存在的问题与风险

### 7.1 高优先级问题

| # | 问题 | 类型 | 影响 | 建议 |
|---|------|------|------|------|
| 1 | **测试失败** — `test_health_check_with_client` 因 event loop 管理失败 | Bug | 测试可靠性 | 修复测试中 Redis mock 的 event loop 管理 |
| 2 | **70 个 ruff 告警** — 大量未使用导入 | 代码质量 | 代码整洁度 | 运行 `ruff check --fix .` 自动修复 |
| 3 | **注册页面缺失** — 前端无 `/register` 页面 | 功能缺失 | 新用户无法自助注册 | 实现注册页面 |
| 4 | **前端无测试** — 完全没有前端自动化测试 | 测试缺失 | 质量保障不足 | 添加 Jest/Vitest + Testing Library |

### 7.2 中优先级问题

| # | 问题 | 类型 | 影响 | 建议 |
|---|------|------|------|------|
| 5 | **速率限制故障开放** — Redis 不可用时所有请求放行 | 安全 | 潜在滥用风险 | 配置为故障关闭（deny-by-default）或内存回退 |
| 6 | **WebSocket 轮询模式** — 非交易所原生 WebSocket | 性能 | 数据延迟（≥5 秒） | 升级为交易所 WebSocket API |
| 7 | **回测结果展示** — 前端回测页面可能不完整 | 功能 | 用户体验 | 完善权益曲线图表、交易明细表等 |
| 8 | **同步状态/调度器前端页面** — 后端 API 存在但前端未对接 | 功能 | 运维能力不足 | 添加同步状态管理和调度器监控面板 |
| 9 | **无幂等性控制** — API 端点无幂等键 | 可靠性 | 重复提交风险 | 关键操作添加 idempotency key |

### 7.3 低优先级问题

| # | 问题 | 类型 | 影响 | 建议 |
|---|------|------|------|------|
| 10 | **前端错误边界** — 无 React Error Boundary | UX | 运行时错误白屏 | 添加全局 + 页面级 Error Boundary |
| 11 | **Hooks 目录空** — `src/hooks/` 无内容 | 架构 | 代码复用不足 | 提取通用逻辑为自定义 Hook |
| 12 | **回测仅支持单标的** — 不支持多标的/组合回测 | 功能 | 量化分析受限 | Phase 2 后续实现 |
| 13 | **无技术指标库** — 策略依赖手动计算 | 功能 | 策略开发效率低 | 集成 ta-lib 或 pandas-ta |
| 14 | **`aiohttp` DeprecationWarning** — Python 3.13 兼容性 | 兼容性 | 日志噪音，未来版本可能出错 | 升级 aiohttp 版本 |

---

## 八、各阶段完成度总览

### Phase 1: 基础设施 ✅ 100%

- [x] FastAPI 后端框架
- [x] PostgreSQL + TimescaleDB + Redis
- [x] CCXT 市场数据接入
- [x] WebSocket 实时流式推送（轮询模式）
- [x] 同步状态管理（SyncStateService）
- [x] 自动回填 & 缺口检测
- [x] APScheduler 定时任务集成
- [x] 数据库迁移（Alembic）

### Phase 2: 量化引擎 🔄 ~75%

- [x] BaseStrategy 策略基类
- [x] 事件驱动回测引擎
- [x] 性能指标计算（Sharpe/Sortino/MaxDD/WinRate）
- [x] 示例策略（MA 交叉、RSI 均值回归）
- [x] ExchangeSimulator（佣金/滑点/止损止盈）
- [x] 回测 API 端点
- [ ] 技术指标库集成
- [ ] 策略优化（参数扫描/遗传算法）
- [ ] 多标的/组合回测
- [ ] 策略持久化与版本管理

### Phase 2.5: 安全与鉴权 ✅ 100%

- [x] JWT Token 认证
- [x] API Key 管理
- [x] 用户 CRUD
- [x] Redis 滑动窗口速率限制
- [x] 超级用户权限控制

### Phase 3: AI Agent 集成 ❌ 0%

- [ ] LangGraph 集成
- [ ] Agent 工具（MarketDataTool、BacktestTool 等）
- [ ] RAG 记忆系统（pgvector）
- [ ] Agent 决策日志
- [ ] 自然语言策略定义

### Phase 4: 实盘交易与风控 ❌ 0%

- [ ] 订单管理系统（OMS）
- [ ] 风控引擎与断路器
- [ ] 实盘交易所 API 对接
- [ ] 组合跟踪
- [ ] 盈亏报告

### 前端仪表盘 🔄 ~60%

- [x] Next.js 项目搭建 + TypeScript
- [x] ShadcnUI 组件库配置（20 个组件）
- [x] Tailwind CSS 4 + 暗色模式
- [x] Zustand 状态管理
- [x] Axios + React Query 数据获取
- [x] 登录页面
- [x] 仪表盘布局（侧边栏导航 + 响应式）
- [x] 市场浏览页（搜索/过滤/同步）
- [x] K 线图表页（OHLCV + WebSocket）
- [x] 回测页面配置面板
- [ ] 注册页面
- [ ] 回测结果完整展示
- [ ] 同步状态管理页
- [ ] 调度器监控页
- [ ] 错误边界处理

---

## 九、建议优先处理事项

### 立即可做（低成本高收益）

1. **执行 `ruff check --fix .`** — 一键修复 51 个未使用导入告警
2. **修复 `test_health_check_with_client`** — 调整测试中 Redis mock 的 event loop 管理
3. **实现注册页面** — 已有 API 和类型定义，只需前端页面

### 短期改进

4. **完善回测结果展示** — 权益曲线图表、交易记录表格、性能指标卡片
5. **添加同步状态管理前端页面** — 后端 API 完整，对接即可
6. **添加前端错误边界** — 防止运行时错误白屏

### 中期规划

7. **升级 WebSocket 为交易所原生模式** — 降低数据延迟
8. **集成技术指标库** — 提升策略开发效率
9. **添加前端测试** — Jest/Vitest + Testing Library
10. **开始 AI Agent 原型** — LangGraph 基础框架搭建

---

## 附录：文件大小分布（后端 Top 15）

| 文件 | 行数 | 说明 |
|------|------|------|
| `scheduler/jobs.py` | 641 | 定时任务定义（最大文件） |
| `api/v1/sync.py` | 482 | 同步相关 API |
| `services/sync_state_service.py` | 480 | 同步状态服务 |
| `strategy/backtest.py` | 458 | 回测引擎 |
| `strategy/exchange_sim.py` | 430 | 交易所模拟器 |
| `api/v1/websocket.py` | 307 | WebSocket 管理 |
| `api/v1/auth.py` | 297 | 认证 API |
| `main.py` | 253 | 应用入口 |
| `scheduler/scheduler.py` | 233 | 调度器核心 |
| `scheduler/state.py` | 231 | 调度器状态工具 |
| `strategy/base.py` | 230 | 策略基类 |
| `services/ohlcv_stream.py` | 226 | OHLCV 推送服务 |
| `core/deps.py` | 223 | 鉴权依赖 |
| `services/user_service.py` | 220 | 用户服务 |
| `strategy/examples.py` | 215 | 示例策略 |
