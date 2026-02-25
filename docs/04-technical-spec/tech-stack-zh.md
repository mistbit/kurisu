# Kurisu - 技术选型详解

本文档详细阐述了 **Kurisu** 项目的技术选型理由，旨在帮助开发者理解系统的设计哲学，并为后续的开发提供理论指导。

---

## 技术选型与决策理由

我们将采用 **"现代 AI 原生栈" (Modern AI-Native Stack)**，即以 Python 为核心后端（因为 AI 生态），以高性能 TypeScript 为前端，结合向量数据库和时序数据库。

### 1. 后端 (Backend): Python + FastAPI
*   **选择**: **FastAPI** (Python 3.10+)
*   **理由**:
    *   **AI 生态统治力**: Python 是 AI/ML 的绝对标准，所有主流库 (PyTorch, TensorFlow, LangChain) 均优先支持 Python。
    *   **高性能异步**: 量化交易需要处理大量并发 I/O（如 WebSocket 行情推送），FastAPI 基于 Starlette 和 Pydantic，性能接近 Go/Node.js，远超 Flask/Django。
    *   **类型安全**: 强制使用 Python Type Hints，减少运行时错误，这对金融系统至关重要。
    *   **自动文档**: 自动生成 Swagger UI，方便前端对接和调试。

### 2. 前端 (Frontend): Next.js + TypeScript
*   **选择**: **Next.js** (React 框架) + **TypeScript**
*   **理由**:
    *   **全栈能力**: Next.js 提供了优秀的服务端渲染 (SSR) 和 API 路由能力，适合构建复杂的仪表盘。
    *   **类型安全**: TypeScript 在编译阶段捕获错误，保证前端代码的健壮性。
    *   **UI 生态**: 配合 **Tailwind CSS** 和 **ShadcnUI** (基于 Radix UI)，可以极快地构建出专业、美观的金融终端界面。
    *   **数据可视化**: React 生态拥有最丰富的图表库 (Recharts, TradingView Lightweight Charts)，适合绘制 K 线图和回测曲线。

### 3. 数据库 (Database): "分层演进" 策略

基于客观的业界规范与量化交易经验，我们采取**“初期灵活性优先，长期高性能演进”**的存储架构。

#### 核心选型：PostgreSQL 18 + TimescaleDB + pgvector
*   **理由**: 
    *   **架构一致性**: 在系统初期，将**交易订单 (关系型)**、**行情数据 (时序型)** 和 **Agent 记忆 (向量型)** 统一存储在 PostgreSQL 18 中，可以极大降低运维成本，并允许通过标准 SQL 进行复杂的跨表关联查询（如：查询某次交易下单时的 AI 决策背景）。
    *   **AI 原生优化**: PostgreSQL 18 针对向量搜索和 AI 任务进行了内核级优化，配合 `pgvector` 插件，是目前 AI + 数据库结合的最佳实践。
    *   **时序扩展**: TimescaleDB 提供了自动分区（Hypertables）和持续聚合功能，足以应对分钟级及以上的量化行情需求。

#### 缓存与消息中心：Redis / Valkey
*   **理由**: 
    *   **低延迟分发**: 业界公认的实时行情分发（Pub/Sub）和热数据缓存标准。
    *   **原子性操作**: 利用 Redis 的原子计数器和分布式锁实现高并发下的风控逻辑。

#### 架构演进路径 (Future Scaling)
为了保持客观的扩展性，系统架构设计将解耦数据访问层，预留以下升级路径：
1.  **大规模回测**: 若未来涉及 Tick 级或全市场海量因子回测，将引入 **ClickHouse** 作为专用分析引擎。
2.  **高性能行情流**: 若需处理极高频行情，将引入 **Kafka** 作为消息总线。
3.  **海量向量检索**: 若 Agent 长期记忆达到亿级规模，将迁移至 **Milvus** 或 **Pinecone** 等专用向量数据库。

### 4. AI 编排 (AI Orchestration): LangChain + LangGraph
*   **选择**: **LangGraph** (构建有状态 Agent)
*   **理由**:
    *   传统的 LangChain 链 (Chain) 是有向无环图 (DAG)，适合简单任务。
    *   **Agent 需要循环 (Loops)**：真实的 Agent 需要 "思考 -> 执行 -> 观察 -> 再思考" 的循环能力。LangGraph 专为此设计，支持状态持久化、人类介入 (Human-in-the-loop) 和多 Agent 协作。

### 5. 量化引擎 (Quant Engine): Pandas + VectorBT / Backtrader
*   **核心库**: **Pandas**, **NumPy**
*   **回测框架**: 自研轻量级事件驱动引擎 或 **VectorBT** (向量化回测，速度极快)。
*   **理由**: Pandas 是数据处理的通用标准。初期建议自研一个简单的事件驱动回测框架，以便彻底理解回测原理（滑点、撮合、资金管理），后期可引入 VectorBT 进行大规模参数扫描。
