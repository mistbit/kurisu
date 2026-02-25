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

### 3. 数据库 (Database): "混合存储" 策略
*   **时序数据 (Market Data)**: **PostgreSQL + TimescaleDB**
    *   **理由**: 量化交易的核心是时间序列数据 (OHLCV)。TimescaleDB 是基于 PG 的插件，兼具 SQL 的查询能力和 NoSQL 的写入性能，支持自动分区和降采样。
*   **向量数据 (AI Memory)**: **pgvector** (PostgreSQL 扩展) 或 **ChromaDB**
    *   **理由**: 为了让 Agent 拥有"记忆"，我们需要存储文本嵌入 (Embeddings)。pgvector 允许我们将向量数据与 business 数据存储在同一个 PG 实例中，简化架构；ChromaDB 则更专用于 AI，开发体验极佳。初步建议使用 **pgvector** 以保持架构精简。
*   **缓存与消息队列**: **Redis**
    *   **理由**: 用于缓存实时行情、存储 Celery 任务队列以及 Pub/Sub 消息分发。

### 4. AI 编排 (AI Orchestration): LangChain + LangGraph
*   **选择**: **LangGraph** (构建有状态 Agent)
*   **理由**:
    *   传统的 LangChain 链 (Chain) 是有向无环图 (DAG)，适合简单任务。
    *   **Agent 需要循环 (Loops)**：真实的 Agent 需要 "思考 -> 执行 -> 观察 -> 再思考" 的循环能力。LangGraph 专为此设计，支持状态持久化、人类介入 (Human-in-the-loop) 和多 Agent 协作。

### 5. 量化引擎 (Quant Engine): Pandas + VectorBT / Backtrader
*   **核心库**: **Pandas**, **NumPy**
*   **回测框架**: 自研轻量级事件驱动引擎 或 **VectorBT** (向量化回测，速度极快)。
*   **理由**: Pandas 是数据处理的通用标准。初期建议自研一个简单的事件驱动回测框架，以便彻底理解回测原理（滑点、撮合、资金管理），后期可引入 VectorBT 进行大规模参数扫描。
