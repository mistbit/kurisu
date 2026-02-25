# 项目基础设施搭建规范 (Project Infrastructure Setup Spec)

## 为什么 (Why)
为了启动 Kurisu 项目，我们需要一个坚实的基础。这包括搭建核心后端框架 (FastAPI)，以及集成用于访问市场数据的 CCXT 库。由于数据库 (PostgreSQL/TimescaleDB) 和缓存 (Redis) 已采用阿里云托管服务，本项目侧重于应用程序的配置与连接。

## 变更内容 (What Changes)
- **目录结构**: 采用 `backend/` 和 `frontend/` 分离的 monorepo 布局。
- **后端框架**: 创建标准的 FastAPI 项目布局于 `backend/` 目录下。
- **依赖管理**: 在 `backend/` 目录下创建 `requirements.txt`，包含 `fastapi`, `uvicorn`, `sqlalchemy`, `asyncpg`, `pydantic-settings`, `ccxt`, `redis` 等。
- **配置管理**: 使用 `pydantic-settings` 实现 `backend/app/core/config.py` 以管理环境变量，支持外部服务连接。
- **数据库连接**: 实现 `backend/app/core/database.py` 用于异步连接到阿里云 PostgreSQL。
- **Redis 连接**: 实现 Redis 客户端连接到阿里云 Redis。
- **健康检查**: 添加一个简单的健康检查端点以验证与外部服务的连接。
- **CCXT 集成**: 创建一个基础服务或工具类来初始化 CCXT 交易所。

## 影响 (Impact)
- **受影响的规范**: 无 (初始设置)。
- **受影响的代码**:
  - 新增目录: `backend/`, `frontend/`。
  - 新增文件: `backend/app/*`, `backend/tests/*`, `backend/.env.example`, `backend/requirements.txt`。

## 新增需求 (ADDED Requirements)

### 需求: 外部服务集成 (Requirement: External Service Integration)
系统应通过环境变量配置连接到外部托管的 TimescaleDB 和 Redis 服务。
- **PostgreSQL/TimescaleDB**: 支持配置 Host, Port, User, Password, DB Name。
- **Redis**: 支持配置 Host, Port, Password, DB Index。

### 需求: FastAPI 后端 (Requirement: FastAPI Backend)
系统应提供一个 FastAPI 应用程序入口点。
- **端点**: `GET /health` 返回 `{"status": "ok"}` 以及数据库/Redis 连接状态。
- **配置**: 从 `.env` 加载设置。

### 需求: 数据库连接 (Requirement: Database Connectivity)
系统应能够异步连接到外部 PostgreSQL 数据库。
- **ORM**: SQLAlchemy (Async) + asyncpg。

### 需求: CCXT 集成 (Requirement: CCXT Integration)
系统应能够导入并实例化 CCXT 交易所对象。
