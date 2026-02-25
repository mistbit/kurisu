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

### 3. Database: "Hybrid Storage" Strategy
*   **Time-Series Data (Market Data)**: **PostgreSQL + TimescaleDB**
    *   **Rationale**: The core of quantitative trading is time-series data (OHLCV). TimescaleDB is a PG plugin that combines SQL query capabilities with NoSQL write performance, supporting automatic partitioning and downsampling.
*   **Vector Data (AI Memory)**: **pgvector** (PostgreSQL extension) or **ChromaDB**
    *   **Rationale**: To give the Agent "memory," we need to store text embeddings. pgvector allows storing vector data alongside business data in the same PG instance, simplifying the architecture; ChromaDB is more specialized for AI with an excellent developer experience. Initially, we recommend **pgvector** to keep the architecture lean.
*   **Cache & Message Queue**: **Redis**
    *   **Rationale**: Used for caching real-time market data, storing Celery task queues, and Pub/Sub message distribution.

### 4. AI Orchestration: LangChain + LangGraph
*   **Choice**: **LangGraph** (Building Stateful Agents)
*   **Rationale**:
    *   Traditional LangChain Chains are Directed Acyclic Graphs (DAGs), suitable for simple tasks.
    *   **Agents Need Loops**: Real Agents need the ability to loop: "Think -> Act -> Observe -> Think Again." LangGraph is designed for this, supporting state persistence, Human-in-the-loop, and multi-agent collaboration.

### 5. Quant Engine: Pandas + VectorBT / Backtrader
*   **Core Libraries**: **Pandas**, **NumPy**
*   **Backtesting Framework**: Custom lightweight event-driven engine or **VectorBT** (vectorized backtesting, extremely fast).
*   **Rationale**: Pandas is the universal standard for data processing. Initially, we recommend building a simple event-driven backtesting engine to thoroughly understand backtesting principles (slippage, matching, money management), and later introducing VectorBT for large-scale parameter scanning.
