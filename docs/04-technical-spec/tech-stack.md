# Kurisu - Technology Stack & Rationale

This document details the **Kurisu** project's technology choices, aiming to help developers understand the design philosophy and provide theoretical guidance for subsequent development.

---

## Technology Stack & Rationale

We will adopt a **"Modern AI-Native Stack"**, with Python as the core backend (due to the AI ecosystem), high-performance TypeScript as the frontend, combined with vector databases and time-series databases.

### 1. Backend: Python + FastAPI
*   **Choice**: **FastAPI** (Python 3.10+)
*   **Rationale**:
    *   **AI Ecosystem Dominance**: Python is the absolute standard for AI/ML; all major libraries (PyTorch, TensorFlow, LangChain) prioritize Python support.
    *   **High-Performance Async**: Quantitative trading requires handling massive concurrent I/O (e.g., WebSocket market data streams). FastAPI, based on Starlette and Pydantic, offers performance close to Go/Node.js, far surpassing Flask/Django.
    *   **Type Safety**: Enforces Python Type Hints, reducing runtime errors, which is critical for financial systems.
    *   **Automatic Documentation**: Generates Swagger UI automatically, facilitating frontend integration and debugging.

### 2. Frontend: Next.js + TypeScript
*   **Choice**: **Next.js** (React Framework) + **TypeScript**
*   **Rationale**:
    *   **Full-Stack Capabilities**: Next.js provides excellent Server-Side Rendering (SSR) and API routing capabilities, suitable for building complex dashboards.
    *   **Type Safety**: TypeScript catches errors at compile time, ensuring robust frontend code.
    *   **UI Ecosystem**: Combined with **Tailwind CSS** and **ShadcnUI** (based on Radix UI), it enables rapid development of professional, beautiful financial terminal interfaces.
    *   **Data Visualization**: The React ecosystem boasts the richest chart libraries (Recharts, TradingView Lightweight Charts), ideal for rendering candlestick charts and backtest curves.

### 3. Database: "Layered Evolution" Strategy

Based on objective industry standards and quantitative trading experience, we adopt a **"Flexibility First, Long-term Performance Evolution"** storage architecture.

#### Core Selection: PostgreSQL 18 + TimescaleDB + pgvector
*   **Rationale**: 
    *   **Architectural Consistency**: In the initial stage, storing **Trading Orders (Relational)**, **Market Data (Time-series)**, and **Agent Memory (Vector)** together in PostgreSQL 18 significantly reduces maintenance costs and allows complex cross-table queries via standard SQL (e.g., querying the AI decision context at the time of a trade).
    *   **AI-Native Optimization**: PostgreSQL 18 features kernel-level optimizations for vector search and AI tasks, making it a best practice when combined with the `pgvector` plugin.
    *   **Time-series Scalability**: TimescaleDB provides automatic partitioning (Hypertables) and continuous aggregates, sufficient for minute-level and higher-frequency quantitative data.

#### Cache & Message Center: Redis / Valkey
*   **Rationale**: 
    *   **Low-latency Distribution**: The industry standard for real-time market data distribution (Pub/Sub) and hot data caching.
    *   **Atomic Operations**: Uses Redis atomic counters and distributed locks for risk control logic under high concurrency.

#### Future Scaling Path
To maintain objective scalability, the system architecture decouples the data access layer, reserving the following upgrade paths:
1.  **Large-scale Backtesting**: If future requirements involve Tick-level or market-wide factor backtesting, **ClickHouse** will be introduced as a dedicated analytical engine.
2.  **High-performance Market Data Streams**: If extremely high-frequency market data needs processing, **Kafka** will be introduced as the message bus.
3.  **Massive Vector Retrieval**: If Agent long-term memory reaches the billion-scale, migration to dedicated vector databases like **Milvus** or **Pinecone** will be considered.

### 4. AI Orchestration: LangChain + LangGraph
*   **Choice**: **LangGraph** (Building Stateful Agents)
*   **Rationale**:
    *   Traditional LangChain Chains are Directed Acyclic Graphs (DAGs), suitable for simple tasks.
    *   **Agents Need Loops**: Real Agents need the ability to loop: "Think -> Act -> Observe -> Think Again." LangGraph is designed for this, supporting state persistence, Human-in-the-loop, and multi-agent collaboration.

### 5. Quant Engine: Pandas + VectorBT / Backtrader
*   **Core Libraries**: **Pandas**, **NumPy**
*   **Backtesting Framework**: Custom lightweight event-driven engine or **VectorBT** (vectorized backtesting, extremely fast).
*   **Rationale**: Pandas is the universal standard for data processing. Initially, we recommend building a simple event-driven backtesting engine to thoroughly understand backtesting principles (slippage, matching, money management), and later introducing VectorBT for large-scale parameter scanning.
