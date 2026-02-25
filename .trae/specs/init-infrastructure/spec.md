# Project Infrastructure Setup Spec

## Why
To initiate the Kurisu project, we need a robust foundation. This includes setting up the core backend framework (FastAPI), the database infrastructure (TimescaleDB & Redis) for storing market data and handling caching/messaging, and integrating the CCXT library for market data access. This corresponds to Phase 1 of the roadmap.

## What Changes
- **Directory Structure**: Create a standard FastAPI project layout.
- **Docker Compose**: Add `docker-compose.yml` for TimescaleDB and Redis.
- **Dependencies**: Create `pyproject.toml` (or `requirements.txt`) with `fastapi`, `uvicorn`, `sqlalchemy`, `asyncpg`, `alembic`, `pydantic-settings`, `ccxt`, `redis`.
- **Configuration**: Implement `app/core/config.py` using `pydantic-settings` to manage environment variables.
- **Database Connection**: Implement `app/core/database.py` for async database connection.
- **Health Check**: Add a simple health check endpoint to verify the setup.
- **CCXT Integration**: Create a basic service or utility to initialize CCXT exchanges.

## Impact
- **Affected specs**: None (Initial setup).
- **Affected code**:
  - New files: `app/*`, `docker-compose.yml`, `.env.example`, `requirements.txt`/`pyproject.toml`.

## ADDED Requirements

### Requirement: Infrastructure Setup
The system SHALL provide a dockerized environment for TimescaleDB and Redis.
- **TimescaleDB**: Based on PostgreSQL 18.
- **Redis**: Latest stable version.

### Requirement: FastAPI Backend
The system SHALL provide a FastAPI application entry point.
- **Endpoint**: `GET /health` returns `{"status": "ok"}`.
- **Configuration**: Loads settings from `.env`.

### Requirement: Database Connectivity
The system SHALL be able to connect to TimescaleDB asynchronously.
- **ORM**: SQLAlchemy (Async) or raw asyncpg (SQLAlchemy recommended for maintainability).

### Requirement: CCXT Integration
The system SHALL be able to import and instantiate CCXT exchanges.
