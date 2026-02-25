# Tasks

- [ ] Task 1: Create project directory structure and basic files
  - [ ] SubTask 1.1: Create directories: `app/api`, `app/core`, `app/models`, `app/services`, `tests`
  - [ ] SubTask 1.2: Create `__init__.py` files
  - [ ] SubTask 1.3: Create `requirements.txt` with dependencies: `fastapi`, `uvicorn`, `sqlalchemy`, `asyncpg`, `alembic`, `pydantic-settings`, `ccxt`, `redis`

- [ ] Task 2: Setup Database Infrastructure with Docker Compose
  - [ ] SubTask 2.1: Create `docker-compose.yml` with `timescale/timescaledb:latest-pg18` and `redis:latest`
  - [ ] SubTask 2.2: Configure environment variables for database credentials in `.env.example`

- [ ] Task 3: Implement Configuration Management
  - [ ] SubTask 3.1: Create `app/core/config.py` using `pydantic-settings` to load `.env` variables
  - [ ] SubTask 3.2: Define `Settings` class with database URL, redis URL, and other config

- [ ] Task 4: Implement Database Connection
  - [ ] SubTask 4.1: Create `app/core/database.py` using `sqlalchemy.ext.asyncio`
  - [ ] SubTask 4.2: Create `get_db` dependency for FastAPI

- [ ] Task 5: Implement CCXT Service Stub
  - [ ] SubTask 5.1: Create `app/services/exchange.py` to handle CCXT exchange initialization (simple factory or singleton)

- [ ] Task 6: Create Main Application Entry Point
  - [ ] SubTask 6.1: Create `app/main.py` with FastAPI app instance
  - [ ] SubTask 6.2: Add `/health` endpoint
  - [ ] SubTask 6.3: Add startup/shutdown events for database connection

# Task Dependencies
- Task 3 depends on Task 1
- Task 4 depends on Task 3 and Task 2
- Task 6 depends on Task 4 and Task 5
