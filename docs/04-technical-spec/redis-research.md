# Redis Research and Competitive Analysis

This document provides an overview of **Redis** and compares it with other in-memory data stores to justify its selection for the **Kurisu** project.

## 1. Introduction to Redis

Redis (Remote Dictionary Server) is an open-source, in-memory data structure store used as a database, cache, message broker, and streaming engine. In a quantitative trading system like Kurisu, Redis plays a critical role in handling real-time data with sub-millisecond latency.

### Core Usage in Kurisu
- **Real-time Market Data Cache**: Storing the latest ticker prices, order book snapshots, and trade events for instant access by strategies and AI Agents.
- **Task Queue (Celery/RQ)**: Managing asynchronous tasks like historical data downloading, backtest execution, and order submission.
- **Pub/Sub Messaging**: Distributing market events from data connectors to multiple strategy subscribers.
- **Session & State Management**: Storing Agent conversation states and temporary strategy variables.

## 2. Competitive Analysis

While Redis is the industry standard, several alternatives have emerged, focusing on multi-threading or different licensing models.

| Feature | Redis | Valkey | Dragonfly | KeyDB | Memcached |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Architecture** | Single-threaded (mostly) | Redis Fork (Open Source) | Multi-threaded (Shared-nothing) | Multi-threaded | Multi-threaded |
| **Data Structures** | Rich (Strings, Lists, Sets, etc.) | Same as Redis | Redis Compatible | Redis Compatible | Simple (Key-Value only) |
| **Performance** | High (100k+ OPS) | Same as Redis | **Extreme (1M+ OPS)** | Very High | High |
| **Persistence** | RDB & AOF | RDB & AOF | Snapshotting | RDB & AOF | None (Memory only) |
| **Licensing** | RSALv2/SSPL (Non-OSI) | **BSD (Open Source)** | BSL | BSD | BSD |
| **Ecosystem** | **Dominant** | Growing (Community-led) | Emerging | Stable | Mature but limited |

### Detailed Breakdown

- **Valkey**: A direct fork of Redis created by the community (Linux Foundation) after Redis changed its license in 2024. It is 100% compatible and a safer long-term choice for pure open-source advocates.
- **Dragonfly**: Designed for modern multi-core hardware. It can achieve 25x the throughput of Redis on a single instance. However, for most quantitative trading setups, Redis's single-threaded performance is already more than sufficient, and Dragonfly's ecosystem is still maturing.
- **KeyDB**: Another multi-threaded fork of Redis. It offers features like active-active replication, but development has slowed down compared to newer alternatives.
- **Memcached**: Extremely simple and fast for basic caching, but lacks the complex data structures (like Sorted Sets for time-series or Streams) that are essential for trading systems.

## 3. Why Redis for Kurisu?

For the **Kurisu** project, Redis remains the most pragmatic choice:

1. **Rich Data Structures**: We use **Sorted Sets** to store time-ordered market data and **Streams** for event-driven processing. Most competitors don't match the maturity of these features.
2. **AI Ecosystem**: Many AI orchestration frameworks (like LangChain/LangGraph) have first-class support for Redis as a memory store.
3. **Python Compatibility**: `redis-py` is one of the most stable and well-documented Python libraries, supporting both synchronous and asynchronous (asyncio) operations.
4. **Alibaba Cloud Support**: Alibaba Cloud offers a highly optimized "ApsaraDB for Redis" service with built-in high availability and monitoring, making cloud deployment trivial.

## 4. Industry Usage

- **High-Frequency Trading**: Used as a low-latency "hot" data layer before persisting to disk-based databases like TimescaleDB.
- **Exchange Connectors**: Buffering market data streams from WebSockets before they are processed by trading logic.
- **Dashboarding**: Powering real-time UI updates for trading terminals.
