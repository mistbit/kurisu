# TimescaleDB Research and Competitive Analysis

This document provides a comprehensive overview of **TimescaleDB** and compares it with other leading time-series databases (TSDBs) to justify its selection for the **Kurisu** project.

## 1. Introduction to TimescaleDB

TimescaleDB is an open-source time-series database built as an extension of **PostgreSQL**. It provides the best of both worlds: the reliability and ecosystem of a relational database and the performance scaling required for time-series data.

### Core Concepts
- **Hypertables**: The primary abstraction in TimescaleDB. To the user, a hypertable looks like a standard PostgreSQL table, but it is automatically partitioned into "chunks" based on time (and optionally other columns) behind the scenes.
- **Continuous Aggregates**: Automatically maintained materialized views for time-series data. Perfect for downsampling market data (e.g., 1m to 1h candles).
- **Compression**: Native column-oriented compression that can reduce storage footprints by 90%+.
- **Full SQL Support**: Unlike many TSDBs, TimescaleDB supports full SQL, including complex `JOIN`s, window functions, and subqueries.

## 2. Competitive Analysis

In the quantitative trading and IoT sectors, several databases compete for dominance. Below is a comparison of TimescaleDB against its main rivals.

| Feature | TimescaleDB | InfluxDB (v2/v3) | ClickHouse | QuestDB |
| :--- | :--- | :--- | :--- | :--- |
| **Architecture** | PostgreSQL Extension | Native TSDB | OLAP Columnar | Native Columnar |
| **Query Language** | **Standard SQL** | Flux / InfluxQL / SQL | SQL-like | SQL + Time Extensions |
| **Write Performance** | High (1M+ rows/s) | Very High | **Highest** | Very High |
| **Relational JOINs** | **Native / Perfect** | Poor | Good (but complex) | Limited |
| **Ecosystem** | **Vast (PostgreSQL)** | Good | Growing | Emerging |
| **Typical Use Case** | Mixed workloads, Trading | Monitoring, IoT | Large-scale Analytics | High-frequency Trading |

### Detailed Breakdown

- **InfluxDB**: Traditionally the market leader for metrics. Excellent for high-volume, simple data. However, its non-relational nature makes it difficult to store metadata (like strategy configs or user profiles) in the same place.
- **ClickHouse**: An analytical powerhouse. It excels at aggregating billions of rows for backtesting but is harder to manage and not optimized for the single-row updates/deletes often needed in live trading systems.
- **QuestDB**: Focuses on extreme performance and low latency using a vectorized execution engine. It's great for raw speed but lacks the mature ecosystem and relational depth of PostgreSQL.

## 3. Why TimescaleDB for Kurisu?

For a project like **Kurisu** that integrates **AI Agents** and **Quantitative Trading**, TimescaleDB offers unique advantages:

1. **Unified Storage**: We can store market data (TSDB), trading orders (Relational), and Agent memory (Vector via `pgvector`) in a single PostgreSQL instance.
2. **AI Integration**: Since TimescaleDB is PostgreSQL, we can easily use `pgvector` alongside our time-series data, allowing the Agent to query market trends and vector memories in the same SQL statement.
3. **Data Lifecycle**: TimescaleDB’s data retention policies and continuous aggregates make it easy to manage years of historical data while keeping the system responsive.
4. **Developer Experience**: Python libraries like `SQLAlchemy` and `asyncpg` work perfectly with TimescaleDB, significantly reducing development time.

## 4. Industry Usage

- **Quantitative Finance**: Widely used for storing OHLCV data, trade logs, and order book snapshots.
- **Crypto Platforms**: Many DEX/CEX aggregators use it to power their charts and historical API endpoints.
- **FinTech**: Used for fraud detection and real-time transaction monitoring where time-series analysis must be combined with user metadata.
