# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Kurisu** is an AI-Native Quantitative Trading Agent & Research Platform built with a microservices-ready monolith architecture. It bridges Quantitative Finance with Modern AI Agents (LangGraph), featuring a modular strategy engine, cognitive AI agent, and modern dashboard.

## Tech Stack

- **Backend**: FastAPI (Python 3.10+), async SQLAlchemy, PostgreSQL + TimescaleDB, Redis
- **Frontend**: Next.js, TypeScript, Tailwind CSS, ShadcnUI (not yet implemented)
- **Exchange Integration**: CCXT (async_support)
- **AI Framework**: LangChain/LangGraph (not yet implemented)
- **Migrations**: Alembic
- **Testing**: pytest, httpx AsyncClient
- **Linting**: ruff

## Development Commands

### Backend (FastAPI)

```bash
cd backend

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run development server (auto-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or use the provided script
./start.sh

# Run tests
pytest

# Lint code
ruff check .

# Database migrations
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

## Backend Architecture

The backend follows a modular structure in `backend/app/`:

```
app/
├── api/              # API Routes (currently minimal, routes are in main.py)
├── core/             # Config, Database, Redis connections
│   ├── config.py     # Pydantic Settings for env vars
│   ├── database.py   # SQLAlchemy async engine and session
│   └── redis.py      # Redis client
├── models/           # SQLAlchemy ORM models
│   ├── market.py     # Market, OHLCV, Trade models
│   ├── account.py    # Account-related models
│   ├── order.py      # Order-related models
│   └── strategy.py   # Strategy-related models
└── services/         # Business logic layer
    └── exchange.py   # ExchangeService, MarketService, MarketDataService
```

### Key Patterns

**Database Access**: All database operations use async SQLAlchemy with dependency injection via `get_db()` from `app.core.database`.

**Settings**: Configuration uses `pydantic-settings` with computed fields for `DATABASE_URL` and `REDIS_URL`. Environment variables are loaded from `.env` (see `.env.example`).

**Exchange Integration**: `ExchangeService` wraps CCXT async client with initialization/cleanup lifecycle. `MarketService` handles market metadata sync with upsert logic. `MarketDataService` handles OHLCV history backfill with pagination.

**API Structure**: Routes are defined in `app/main.py` (currently). They use FastAPI dependency injection for database sessions (`Depends(get_db)`) and exchange services (`Depends(get_exchange_service)`).

**Time Handling**: All timestamps use UTC timezone. Conversion utilities `_ensure_utc()`, `_to_ms()`, and `_to_datetime()` are defined in `app/main.py` for consistency.

**Upsert Pattern**: Database upserts use SQLAlchemy's `insert().on_conflict_do_update()` with unique constraints on composite keys (e.g., `(exchange, symbol)`, `(time, market_id, timeframe)`).

### Database Models

- `Market`: Trading pairs with exchange, symbol, base/quote assets, and precision info. Unique constraint on `(exchange, symbol)`.
- `OHLCV`: Time-series candle data. Composite primary key on `(time, market_id, timeframe)`. Uses TimescaleDB hypertable for efficient time-series queries.
- `Trade`: Individual trade records with composite primary key on `(time, market_id, trade_id)`.

### Services

- `ExchangeService`: CCXT wrapper with async initialization, markets/ticker/balance/OHLCV fetching.
- `MarketService`: Syncs market metadata from exchange to database with allowlist/denylist filtering.
- `MarketDataService`: Fetches historical OHLCV data with automatic pagination and batch upsert.

## API Endpoints

- `GET /health` / `GET /api/v1/health`: Health check verifying DB and Redis connections
- `GET /api/v1/version`: App version
- `GET /api/v1/markets`: List markets with filtering (exchange, symbol, active, pagination)
- `GET /api/v1/markets/{market_id}`: Get specific market details
- `POST /api/v1/markets/sync`: Trigger market metadata sync (with optional quote allowlist/denylist)
- `GET /api/v1/data/ohlcv`: Query OHLCV data by market_id, timeframe, time range (returns `[timestamp_ms, open, high, low, close, volume]` format)

## Testing

Tests use pytest with httpx `AsyncClient` for testing FastAPI endpoints. Dependencies like `get_db` and `redis_client.ping` are mocked using `app.dependency_overrides` and `AsyncMock`.

See `backend/tests/test_health.py` for examples.

## Agent Architecture (Planned)

The AI agent will follow a cognitive architecture with:
- **Perception Module**: Multi-modal input (text instructions, market data, news)
- **Memory Module**: Short-term (context window) and long-term (RAG with vector DB)
- **Planning Module**: ReAct pattern (Thought -> Action -> Observation)
- **Toolset**: Data tools, analysis tools, trading tools

Agent logic will live in `backend/app/agents/` (not yet implemented).

## Commit Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `refactor`: Code change without new feature/bug fix
- `test`: Adding/correcting tests
- `chore`: Build process or auxiliary tools

Example: `feat(ingestion): add market sync and backfill`
