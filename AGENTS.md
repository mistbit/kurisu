# Repository Guidelines

## Project Structure & Module Organization
`backend/app/` contains the FastAPI codebase, organized into `api/v1`, `core`, `models`, `services`, `scheduler`, and `strategy`. Database migrations live in `backend/alembic/versions/`, and backend tests plus shared fixtures live in `backend/tests/`. `frontend/src/app/` holds Next.js App Router pages, `frontend/src/components/ui/` contains shared UI primitives, `frontend/public/` stores static assets, and `docs/` tracks product, architecture, and testing notes.

## Build, Test, and Development Commands
Backend setup:
`cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`

Run the API with hot reload:
`cd backend && source venv/bin/activate && uvicorn app.main:app --reload`

Apply migrations:
`cd backend && source venv/bin/activate && alembic upgrade head`

Run backend tests:
`cd backend && source venv/bin/activate && python -m pytest tests`

Lint backend code:
`cd backend && source venv/bin/activate && ruff check app tests`

Frontend setup and development:
`cd frontend && npm install`
`npm run dev`, `npm run build`, `npm run lint`

## Coding Style & Naming Conventions
Use 4-space indentation and PEP 8 naming in Python: `snake_case` for modules/functions and `PascalCase` for classes and Pydantic models. Keep FastAPI handlers thin and push business logic into `backend/app/services/`. In the frontend, follow the existing TSX style: React components in `PascalCase`, route folders in lowercase, and shared UI files in kebab-case under `frontend/src/components/ui/`.

## Testing Guidelines
Backend tests use `pytest`, `pytest-asyncio`, and `httpx`, with shared fixtures in `backend/tests/conftest.py`. Name files `test_*.py` and add focused regression coverage for auth, sync, scheduler, websocket, or backtest changes. No coverage gate or frontend test runner is currently configured in the repository, so frontend PRs should include manual verification steps until automated tests are added.

## Commit & Pull Request Guidelines
Recent history follows Conventional Commits such as `fix:` and `docs:`. Prefer scoped messages like `fix(auth): reject expired API keys`. PRs should include a concise summary, linked issue or context, migration or config notes when relevant, and screenshots for UI changes. If API behavior or setup changes, update the matching docs in `README.md`, `CONTRIBUTING.md`, or `docs/`.

## Security & Configuration Tips
Copy `backend/.env.example` to `backend/.env` and keep secrets out of git. Review Alembic migrations carefully before merging, and never hardcode exchange credentials, database passwords, or Redis connection details.
