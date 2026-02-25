# 项目基础设施搭建规范 (Project Infrastructure Setup Spec)

## 为什么 (Why)
为了启动 Kurisu 项目，我们需要一个坚实的基础。这包括搭建核心后端框架 (FastAPI)，用于存储市场数据和处理缓存/消息的数据库基础设施 (TimescaleDB & Redis)，以及集成用于访问市场数据的 CCXT 库。这对应于路线图的第一阶段。

## 变更内容 (What Changes)
- **目录结构**: 创建标准的 FastAPI 项目布局。
- **Docker Compose**: 添加 `docker-compose.yml` 用于部署 TimescaleDB 和 Redis。
- **依赖管理**: 创建 `pyproject.toml` (或 `requirements.txt`)，包含 `fastapi`, `uvicorn`, `sqlalchemy`, `asyncpg`, `alembic`, `pydantic-settings`, `ccxt`, `redis`。
- **配置管理**: 使用 `pydantic-settings` 实现 `app/core/config.py` 以管理环境变量。
- **数据库连接**: 实现 `app/core/database.py` 用于异步数据库连接。
- **健康检查**: 添加一个简单的健康检查端点以验证设置。
- **CCXT 集成**: 创建一个基础服务或工具类来初始化 CCXT 交易所。

## 影响 (Impact)
- **受影响的规范**: 无 (初始设置)。
- **受影响的代码**:
  - 新增文件: `app/*`, `docker-compose.yml`, `.env.example`, `requirements.txt`/`pyproject.toml`.

## 新增需求 (ADDED Requirements)

### 需求: 基础设施搭建 (Requirement: Infrastructure Setup)
系统应提供 TimescaleDB 和 Redis 的 Docker 化环境。
- **TimescaleDB**: 基于 PostgreSQL 18。
- **Redis**: 最新稳定版。

### 需求: FastAPI 后端 (Requirement: FastAPI Backend)
系统应提供一个 FastAPI 应用程序入口点。
- **端点**: `GET /health` 返回 `{"status": "ok"}`。
- **配置**: 从 `.env` 加载设置。

### 需求: 数据库连接 (Requirement: Database Connectivity)
系统应能够异步连接到 TimescaleDB。
- **ORM**: SQLAlchemy (Async) 或原生 asyncpg (推荐使用 SQLAlchemy 以便于维护)。

### 需求: CCXT 集成 (Requirement: CCXT Integration)
系统应能够导入并实例化 CCXT 交易所对象。
