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
- **Scheduler**: APScheduler for background job scheduling

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
├── api/              # API Routes organized by version
│   └── v1/          # v1 API endpoints (sync, scheduler, auth, etc.)
├── core/             # Config, Database, Redis connections
│   ├── config.py     # Pydantic Settings for env vars
│   ├── database.py   # SQLAlchemy async engine and session
│   ├── redis.py      # Redis client
│   └── deps.py       # Authentication dependencies
├── models/           # SQLAlchemy ORM models
│   ├── market.py     # Market, OHLCV, Trade models
│   ├── account.py    # Account, User, APIKey models
│   ├── order.py      # Order-related models
│   ├── strategy.py   # Strategy-related models
│   └── sync_state.py # Data sync state tracking
├── services/         # Business logic layer
│   ├── exchange.py   # ExchangeService, MarketService, MarketDataService
│   ├── sync_state_service.py # SyncStateService for state management
│   ├── auth.py       # JWT token and password utilities
│   ├── user_service.py # User and API key management
│   └── rate_limiter.py # Redis sliding window rate limiting
├── strategy/         # Backtesting engine
│   ├── base.py       # BaseStrategy, Signal, Position models
│   ├── backtest.py   # BacktestEngine, PerformanceCalculator
│   ├── exchange_sim.py # ExchangeSimulator for order execution
│   └── examples.py   # Example strategies (MA, RSI)
└── scheduler/        # Background job scheduling
    ├── scheduler.py  # APScheduler integration
    ├── jobs.py       # Scheduled job definitions
    └── __init__.py   # Module exports
```

### Key Patterns

**Database Access**: All database operations use async SQLAlchemy with dependency injection via `get_db()` from `app.core.database`.

**Settings**: Configuration uses `pydantic-settings` with computed fields for `DATABASE_URL` and `REDIS_URL`. Environment variables are loaded from `.env` (see `.env.example`).

**Exchange Integration**: `ExchangeService` wraps CCXT async client with initialization/cleanup lifecycle. `MarketService` handles market metadata sync with upsert logic. `MarketDataService` handles OHLCV history backfill with pagination.

**API Structure**: Routes are organized in `app/api/v1/` by feature (sync, scheduler, etc.). They use FastAPI dependency injection for database sessions (`Depends(get_db)`) and exchange services (`Depends(get_exchange_service)`).

**Time Handling**: All timestamps use UTC timezone. Conversion utilities `_ensure_utc()`, `_to_ms()`, and `_to_datetime()` are defined in `app/main.py` for consistency.

**Upsert Pattern**: Database upserts use SQLAlchemy's `insert().on_conflict_do_update()` with unique constraints on composite keys (e.g., `(exchange, symbol)`, `(time, market_id, timeframe)`).

**Scheduler Configuration**: Configure background job scheduling behavior:
- `SCHEDULER_ENABLED`: Enable/disable scheduler (default: `true`)
- `AUTO_SYNC_INTERVAL_MINUTES`: Interval for OHLCV auto-sync job (default: `1`)
- `MARKET_SYNC_HOUR`: Hour of day for market metadata sync (0-23, default: `0`)
- `BACKFILL_CHECK_INTERVAL_HOURS`: Interval for backfill gap check (default: `1`)
- `MAX_CONCURRENT_SYNCS`: Maximum concurrent exchange API calls (default: `3`)
- `EXCHANGES`: List of exchanges to sync (default: `["binance"]`)
- `SECRET_KEY`: Secret key for JWT token signing (required in production)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Token expiration time (default: 30)
- `RATE_LIMIT_ENABLED`: Enable/disable rate limiting (default: `true`)
- `RATE_LIMIT_PER_MINUTE`: Default rate limit (default: 100)

**Security Notes**:
- Never use `eval()` for JSON parsing - always use `json.loads()`
- Use SQLAlchemy parameterized queries to prevent SQL injection
- Validate and sanitize all user inputs, especially in API endpoints

### Database Models

- `Market`: Trading pairs with exchange, symbol, base/quote assets, and precision info. Unique constraint on `(exchange, symbol)`.
- `OHLCV`: Time-series candle data. Composite primary key on `(time, market_id, timeframe)`. Uses TimescaleDB hypertable for efficient time-series queries.
- `Trade`: Individual trade records with composite primary key on `(time, market_id, trade_id)`.
- `DataSyncState`: Tracks synchronization progress for each market/timeframe combination. Includes sync status (`idle`, `syncing`, `error`), last sync time, auto-syncing flag, and backfill completion tracking.

### Services

- `ExchangeService`: CCXT wrapper with async initialization, markets/ticker/balance/OHLCV fetching.
- `MarketService`: Syncs market metadata from exchange to database with allowlist/denylist filtering.
- `MarketDataService`: Fetches historical OHLCV data with automatic pagination and batch upsert.
- `SyncStateService`: High-level service for managing data synchronization states. Provides methods for querying, creating, and updating sync state records with Redis caching for performance.
- `UserService`: User and API key management with CRUD operations.
- `RateLimiter`: Redis-based sliding window rate limiting.

### Authentication System

The API supports two authentication methods:

**JWT Token Authentication**:
- Login via `POST /api/v1/auth/login` to get access token
- Include token in `Authorization: Bearer <token>` header
- Tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default: 30)

**API Key Authentication**:
- Create keys via `POST /api/v1/auth/api-keys`
- Include key in `X-API-Key` header
- Keys support custom rate limits and expiration dates

**Authentication Dependencies** (in `app/core/deps.py`):
- `get_current_user`: Requires valid JWT token
- `get_authenticated_user`: Accepts either JWT or API key
- `require_superuser`: Requires superuser privileges
- `check_rate_limit`: Enforces rate limiting

### Backtest Engine

The backtest engine in `app/strategy/` provides:

**BaseStrategy**: Abstract base class for trading strategies
- Implement `generate_signal(bar, symbol)` to create signals
- Use `get_history()`, `get_close_prices()` for historical data
- Track positions via `has_position()`, `get_position()`

**ExchangeSimulator**: Simulates order execution
- Market and limit order support
- Commission and slippage simulation
- Stop-loss and take-profit handling

**BacktestEngine**: Orchestrates backtesting
- Load data via `load_data(symbol, bars)`
- Run via `engine.run(start_date, end_date)`
- Returns `BacktestResult` with performance metrics

**PerformanceCalculator**: Calculates metrics
- Sharpe ratio, Sortino ratio
- Maximum drawdown
- Win rate, profit factor

**Example Strategies** (in `app/strategy/examples.py`):
- `MovingAverageCrossoverStrategy`: Buy/sell on MA crossovers
- `RSIStrategy`: Mean reversion using RSI oversold/overbought

### Scheduler System

The scheduler uses APScheduler for background job execution:

- **Initialization**: Started in FastAPI lifespan if `SCHEDULER_ENABLED=true`
- **Job Store**: Redis (with memory fallback) for persistent job storage
- **Jobs**:
  - `auto_sync_ohlcv`: Fetches latest OHLCV data for auto-syncing markets (runs every `AUTO_SYNC_INTERVAL_MINUTES`)
  - `sync_markets_metadata`: Syncs market metadata from exchanges (runs daily at `MARKET_SYNC_HOUR`)
  - `check_backfill_gaps`: Detects and logs gaps in OHLCV data (runs every `BACKFILL_CHECK_INTERVAL_HOURS`)

**Key Features**:
- Concurrency control via semaphore (`MAX_CONCURRENT_SYNCS`)
- Exchange service connection pooling and caching
- Job timeout handling (default 5 minutes)
- Retry logic with exponential backoff
- Job statistics tracking in Redis
- Automatic gap detection and backfill (gaps ≤ 50 candles)
- Configurable exchange list via `EXCHANGES` setting

## API Endpoints

### Authentication
- `POST /api/v1/auth/register`: Register a new user account
- `POST /api/v1/auth/login`: Login and get JWT access token
- `GET /api/v1/auth/me`: Get current authenticated user info
- `POST /api/v1/auth/password`: Change current user's password
- `POST /api/v1/auth/api-keys`: Create a new API key
- `GET /api/v1/auth/api-keys`: List user's API keys
- `DELETE /api/v1/auth/api-keys/{id}`: Revoke an API key

### Health & Info
- `GET /health` / `GET /api/v1/health`: Health check verifying DB and Redis connections
- `GET /api/v1/version`: App version

### Markets
- `GET /api/v1/markets`: List markets with filtering (exchange, symbol, active, pagination)
- `GET /api/v1/markets/{market_id}`: Get specific market details
- `POST /api/v1/markets/sync`: Trigger market metadata sync (with optional quote allowlist/denylist)

### Data & Synchronization
- `GET /api/v1/data/ohlcv`: Query OHLCV data by market_id, timeframe, time range (returns `[timestamp_ms, open, high, low, close, volume]` format)
- `GET /api/v1/data/sync_state`: List sync states with filtering (market_id, timeframe, sync_status, has_errors, pagination)
- `GET /api/v1/data/sync_state/{sync_state_id}`: Get specific sync state details
- `POST /api/v1/data/backfill`: Trigger backfill task for specified markets and timeframes (runs as background task)
- `GET /api/v1/data/backfill/{task_id}`: Get backfill task status
- `POST /api/v1/data/auto_sync`: Enable or disable auto-syncing for a market and timeframes

### Scheduler
- `GET /api/v1/scheduler/status`: Get scheduler status and job statistics

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
