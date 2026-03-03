"""Pytest configuration and fixtures."""
import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.core.redis import redis_client


# Configure pytest-asyncio
pytest_asyncio_mode = "auto"

# Test database URL (use SQLite for faster tests, or separate PostgreSQL DB)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    # Create only DataSyncState table for now
    from app.models.sync_state import DataSyncState
    from sqlalchemy.schema import CreateTable

    async with engine.begin() as conn:
        await conn.execute(CreateTable(DataSyncState.__table__))
    yield engine
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS data_sync_state"))
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    from sqlalchemy import text

    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        # Clean up before each test
        await session.execute(text("DELETE FROM data_sync_state"))
        await session.commit()
        yield session
        # Clean up after each test
        await session.rollback()
        await session.execute(text("DELETE FROM data_sync_state"))
        await session.commit()


@pytest_asyncio.fixture
async def db_session_factory(test_engine):
    """Provide a factory for creating new sessions."""
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    return async_session


@pytest.fixture
def override_get_db(db_session):
    """Override FastAPI database dependency."""
    async def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(override_get_db) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing FastAPI endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
