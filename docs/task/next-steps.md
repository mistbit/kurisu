# Kurisu 后续任务规划

> 基于项目现状报告（2026-03-11）整理  
> 当前进度：Phase 1 ✅ | Phase 2 ~75% | Phase 2.5 ✅ | Phase 3 ❌ | Phase 4 ❌ | 前端 ~60%

---

## 目录

- [一、立即可做（Quick Wins）](#一立即可做quick-wins)
- [二、Phase 2 量化引擎收尾](#二phase-2-量化引擎收尾)
- [三、前端补全](#三前端补全)
- [四、代码质量与测试](#四代码质量与测试)
- [五、Phase 3 AI Agent 集成](#五phase-3-ai-agent-集成)
- [六、Phase 4 实盘交易与风控](#六phase-4-实盘交易与风控)
- [七、优先级总览](#七优先级总览)

---

## 一、立即可做（Quick Wins）

低成本、高收益的任务，建议第一时间处理。

| # | 任务 | 说明 | 预计工时 |
|---|------|------|----------|
| 1.1 | **Ruff 自动修复** | 执行 `ruff check --fix .` 修复 51 个未使用导入告警 | 5 分钟 |
| 1.2 | **修复失败测试** | `test_health_check_with_client` 因 event loop 管理导致 Redis mock 失败，返回 503 | 0.5-1h |
| 1.3 | **前端注册页面** | 后端 API (`POST /auth/register`) 已就绪，前端 `/register` 路由缺失，登录页已有入口链接 | 1-2h |

---

## 二、Phase 2 量化引擎收尾

当前进度 ~75%，以下是未完成的部分。

### 2.1 技术指标库集成

- **目标**：集成 `pandas-ta` 或 `ta-lib`，取代策略中手动计算指标的方式
- **范围**：
  - 选择并安装指标库（推荐 `pandas-ta`，纯 Python 无 C 依赖）
  - 在 `BaseStrategy` 或独立模块中封装常用指标接口（MA、EMA、RSI、MACD、Bollinger Bands 等）
  - 更新示例策略 `examples.py` 使用新指标接口
  - 编写单元测试验证指标计算正确性
- **预计工时**：4-6h

### 2.2 策略优化功能

- **目标**：支持参数扫描 / 网格搜索 / 遗传算法等优化手段
- **范围**：
  - 参数空间定义（策略参数的范围、步长、类型）
  - 网格搜索（Grid Search）暴力遍历
  - （可选）遗传算法优化器
  - 优化结果排序与可视化输出
  - API 端点 `POST /api/v1/backtest/optimize`
- **预计工时**：8-12h

### 2.3 多标的 / 组合回测

- **目标**：支持同时回测多个交易对，计算组合层面的收益与风险指标
- **范围**：
  - `BacktestEngine` 支持多 symbol 数据加载
  - 组合权重分配逻辑
  - 组合层面绩效指标（组合 Sharpe、相关性矩阵等）
- **预计工时**：6-10h

### 2.4 策略持久化与版本管理

- **目标**：策略代码和回测结果可存储到数据库，支持版本历史
- **范围**：
  - 利用已有 `Strategy` / `StrategyRun` ORM 模型
  - CRUD API 端点（保存策略、列出策略、查看历史运行等）
  - 策略参数快照（每次运行记录当时的参数）
- **预计工时**：4-6h

---

## 三、前端补全

当前进度 ~60%，以下为缺失功能。

### 3.1 注册页面 ⚡ 高优先

- 位置：`src/app/(auth)/register/page.tsx`
- 参考：登录页 `src/app/(auth)/login/page.tsx`
- 字段：用户名、邮箱、密码、确认密码
- 调用：`POST /api/v1/auth/register`

### 3.2 回测结果完整展示 ⚡ 高优先

- 权益曲线图表（Recharts 折线图）
- 绩效指标卡片（Sharpe、Sortino、MaxDD、WinRate、ProfitFactor）
- 交易记录明细表（时间、方向、价格、数量、盈亏）
- 持仓变化时间线

### 3.3 同步状态管理页

- 位置：`src/app/(dashboard)/sync/page.tsx`
- 对接 API：
  - `GET /api/v1/data/sync_state` — 同步状态列表
  - `POST /api/v1/data/auto_sync` — 启用/禁用自动同步
  - `POST /api/v1/data/backfill` — 触发回填
  - `GET /api/v1/data/backfill/{task_id}` — 回填进度
- 功能：展示各市场/时间周期的同步状态、错误信息，操作按钮

### 3.4 调度器监控页

- 位置：`src/app/(dashboard)/scheduler/page.tsx`
- 对接 API：`GET /api/v1/scheduler/status`
- 功能：各定时任务状态、上次/下次执行时间、成功/失败统计

### 3.5 全局错误边界

- 添加 React Error Boundary 组件
- 页面级和全局级两层保护
- 友好的错误提示 + 重试按钮

### 3.6 自定义 Hooks

- `useAuth` — 鉴权状态与登出逻辑
- `useMarkets` — 市场列表查询（React Query）
- `useOHLCV` — K 线数据获取
- `useWebSocket` — WebSocket 连接管理

---

## 四、代码质量与测试

### 4.1 后端测试补全

| 缺失测试 | 优先级 | 说明 |
|----------|--------|------|
| 端到端 API 流程测试 | 高 | 完整的 数据同步 → 回测 流程 |
| 调度器任务单元测试 | 中 | 不含调度的纯任务执行覆盖 |
| 交易所 Mock 连接测试 | 中 | 模拟 CCXT 返回，验证服务层 |
| 异常边界覆盖 | 中 | 网络超时、数据异常、并发冲突 |

### 4.2 前端测试搭建

- 安装 Vitest + Testing Library
- 核心页面组件测试（登录、市场列表、回测表单）
- API 客户端 Mock 测试
- Zustand Store 测试

### 4.3 安全改进

| 问题 | 优先级 | 建议 |
|------|--------|------|
| 速率限制故障开放 | 中 | Redis 不可用时默认放行 → 改为故障关闭或内存回退 |
| API 幂等性 | 低 | 关键写操作添加 Idempotency Key |

### 4.4 性能优化

- **WebSocket 升级**：当前 HTTP 轮询模式（5 秒延迟）→ 交易所原生 WebSocket（CCXT Pro 或直接对接）
- **分页边界校验**：`offset` 参数边界验证

---

## 五、Phase 3 AI Agent 集成

> 对应需求文档 §3.3 AI Agent 核心  
> 对应架构文档 `docs/02-architecture/agent-logic-zh.md`

### 5.1 基础框架搭建

- **目录结构**：
  ```
  backend/app/agents/
  ├── __init__.py
  ├── core.py          # Agent 主循环（LangGraph StateGraph）
  ├── state.py         # Agent 状态定义
  ├── tools/           # 工具集
  │   ├── __init__.py
  │   ├── market_data.py   # get_market_price, get_historical_data
  │   ├── backtest.py      # run_backtest
  │   ├── indicators.py    # calculate_indicator
  │   └── trading.py       # place_order, get_balance（Phase 4）
  ├── memory/          # 记忆模块
  │   ├── __init__.py
  │   ├── short_term.py    # 对话上下文管理
  │   └── long_term.py     # pgvector RAG 检索
  └── prompts/         # Prompt 模板
      ├── __init__.py
      └── templates.py
  ```
- **依赖安装**：`langchain`, `langgraph`, `langchain-openai`（或 `langchain-anthropic`）
- **预计工时**：8-12h

### 5.2 Agent 工具集

| 工具 | 描述 | 对接服务 |
|------|------|----------|
| `MarketDataTool` | 获取实时/历史行情数据 | `ExchangeService`, `MarketDataService` |
| `BacktestTool` | 运行回测并返回绩效报告 | `BacktestEngine` |
| `IndicatorTool` | 计算技术指标 | 指标库（pandas-ta） |
| `SearchTool` | 检索历史交易记录和策略 | RAG / pgvector |

### 5.3 RAG 记忆系统

- 安装 pgvector 扩展
- 定义 Embedding 模型（OpenAI `text-embedding-3-small` 或本地模型）
- 实现文档存储与检索接口
- 存储内容：交易日志、策略解释、市场分析记录

### 5.4 Agent 对话 API

- `POST /api/v1/agent/chat` — 对话入口
- `GET /api/v1/agent/history` — 对话历史
- Server-Sent Events (SSE) 或 WebSocket 流式输出

### 5.5 前端 Agent 聊天界面

- 聊天窗口组件（消息列表 + 输入框）
- 流式输出展示（打字机效果）
- 工具调用可视化（展示 Agent 的思考过程）
- 嵌入式图表（Agent 返回的数据自动渲染）

---

## 六、Phase 4 实盘交易与风控

> 对应需求文档 §3.5 执行引擎

### 6.1 订单管理系统 (OMS)

- 利用已有 `Order`、`Execution`、`Position` ORM 模型
- 订单生命周期管理：创建 → 提交 → 部分成交 → 完全成交 / 取消
- API：`POST /orders`, `GET /orders`, `DELETE /orders/{id}`

### 6.2 风控引擎

- 仓位限制（单标的最大仓位占比）
- 最大回撤熔断（组合回撤超过阈值自动全平）
- 单日亏损限制
- 紧急停止（Kill Switch）API

### 6.3 模拟交易 (Paper Trading)

- 复用 `ExchangeSimulator` 核心逻辑
- 实时接入市场数据驱动模拟
- 独立的模拟账户与资产跟踪

### 6.4 实盘交易所对接

- CCXT 统一下单接口封装
- API Key 加解密存储（已有 `APIKey` 模型）
- 订单状态回调与同步
- 交易所故障降级处理

### 6.5 盈亏报告

- 按日/周/月统计 PnL
- 已实现/未实现盈亏分离
- 导出 CSV / PDF 报告

---

## 七、优先级总览

按推荐执行顺序排列：

### 🔴 P0 — 立即处理

| # | 任务 | 模块 | 工时 |
|---|------|------|------|
| 1 | Ruff 自动修复 (`ruff check --fix .`) | 后端 | 5min |
| 2 | 修复失败测试 `test_health_check_with_client` | 测试 | 0.5-1h |
| 3 | 前端注册页面 | 前端 | 1-2h |

### 🟠 P1 — 短期完成（Phase 2 收尾 + 前端核心）

| # | 任务 | 模块 | 工时 |
|---|------|------|------|
| 4 | 技术指标库集成 (pandas-ta) | 后端 | 4-6h |
| 5 | 回测结果完整展示 | 前端 | 4-6h |
| 6 | 同步状态管理前端页面 | 前端 | 3-4h |
| 7 | 策略持久化与版本管理 | 后端 | 4-6h |
| 8 | 前端错误边界 | 前端 | 1-2h |
| 9 | 调度器监控前端页面 | 前端 | 2-3h |

### 🟡 P2 — 中期迭代（增强功能 + 质量）

| # | 任务 | 模块 | 工时 |
|---|------|------|------|
| 10 | 策略优化功能（参数扫描） | 后端 | 8-12h |
| 11 | 多标的/组合回测 | 后端 | 6-10h |
| 12 | WebSocket 升级为交易所原生 | 后端 | 6-8h |
| 13 | 端到端集成测试 | 测试 | 4-6h |
| 14 | 前端测试搭建 (Vitest) | 前端 | 4-6h |
| 15 | 速率限制故障关闭改进 | 后端 | 1-2h |
| 16 | 自定义 Hooks 提取 | 前端 | 2-3h |

### 🟢 P3 — AI Agent（Phase 3）

| # | 任务 | 模块 | 工时 |
|---|------|------|------|
| 17 | LangGraph 基础框架 + Agent 状态机 | 后端 | 8-12h |
| 18 | Agent 工具集（MarketData/Backtest/Indicator） | 后端 | 6-8h |
| 19 | RAG 记忆系统 (pgvector) | 后端 | 6-8h |
| 20 | Agent 对话 API (SSE/WebSocket) | 后端 | 4-6h |
| 21 | 前端 Agent 聊天界面 | 前端 | 8-12h |

### 🔵 P4 — 实盘交易（Phase 4）

| # | 任务 | 模块 | 工时 |
|---|------|------|------|
| 22 | 订单管理系统 (OMS) | 后端 | 8-12h |
| 23 | 风控引擎与熔断机制 | 后端 | 6-8h |
| 24 | 模拟交易 (Paper Trading) | 后端 | 6-8h |
| 25 | 实盘交易所对接 | 后端 | 8-12h |
| 26 | 盈亏报告与导出 | 后端+前端 | 4-6h |

---

## 附：当前技术债务清单

| 问题 | 严重程度 | 位置 |
|------|----------|------|
| 70 个 ruff 告警（51 可自动修复） | 低 | 全局 |
| 1 个测试失败（event loop） | 中 | `test_sync_integration.py` |
| 速率限制 Redis 故障时默认放行 | 中 | `services/rate_limiter.py` |
| WebSocket 轮询模式延迟 ≥5s | 低 | `services/ohlcv_stream.py` |
| `aiohttp` DeprecationWarning | 低 | Python 3.13 兼容性 |
| 前端 `src/hooks/` 空目录 | 低 | 前端 |
