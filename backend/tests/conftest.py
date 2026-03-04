"""Pytest configuration and fixtures."""
import asyncio
import os
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text, JSON, MetaData, Table, Column, Integer, String, Boolean, Numeric, DateTime, ForeignKey, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.core.database import get_db


# Configure pytest-asyncio
pytest_asyncio_mode = "auto"

# Test database URL (use SQLite for faster tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


def get_test_metadata():
    """Create test metadata with SQLite-compatible column types."""
    metadata = MetaData()

    # Users table
    users = Table(
        'users', metadata,
        Column('id', Integer, primary_key=True),
        Column('username', String(50), unique=True, nullable=False),
        Column('email', String(100), unique=True, nullable=False),
        Column('hashed_password', String(255), nullable=False),
        Column('is_active', Boolean, default=True),
        Column('is_superuser', Boolean, default=False),
        Column('created_at', DateTime(timezone=True), server_default=func.now()),
        Column('updated_at', DateTime(timezone=True), server_default=func.now()),
    )

    # API Keys table
    api_keys = Table(
        'api_keys', metadata,
        Column('id', Integer, primary_key=True),
        Column('user_id', Integer, ForeignKey('users.id'), nullable=False),
        Column('key_hash', String(255), unique=True, nullable=False),
        Column('name', String(100), nullable=False),
        Column('is_active', Boolean, default=True),
        Column('rate_limit', Integer, default=100),
        Column('last_used_at', DateTime(timezone=True), nullable=True),
        Column('created_at', DateTime(timezone=True), server_default=func.now()),
        Column('expires_at', DateTime(timezone=True), nullable=True),
    )

    # Markets table with JSON instead of JSONB
    markets = Table(
        'markets', metadata,
        Column('id', Integer, primary_key=True),
        Column('exchange', String(50), nullable=False),
        Column('symbol', String(50), nullable=False),
        Column('base_asset', String(20), nullable=False),
        Column('quote_asset', String(20), nullable=False),
        Column('active', Boolean, default=True),
        Column('meta', JSON, default={}),
        Column('exchange_symbol', String(50)),
        Column('price_precision', Integer),
        Column('amount_precision', Integer),
    )

    # OHLCV table
    ohlcv = Table(
        'ohlcv', metadata,
        Column('time', DateTime(timezone=True), primary_key=True),
        Column('market_id', Integer, ForeignKey('markets.id'), primary_key=True),
        Column('timeframe', String(10), primary_key=True),
        Column('open', Numeric(20, 10), nullable=False),
        Column('high', Numeric(20, 10), nullable=False),
        Column('low', Numeric(20, 10), nullable=False),
        Column('close', Numeric(20, 10), nullable=False),
        Column('volume', Numeric(20, 10), nullable=False),
    )

    # DataSyncState table
    data_sync_state = Table(
        'data_sync_state', metadata,
        Column('id', Integer, primary_key=True),
        Column('market_id', Integer, ForeignKey('markets.id'), nullable=True),
        Column('exchange', String(50), nullable=False),
        Column('symbol', String(50), nullable=False),
        Column('timeframe', String(10), nullable=False),
        Column('sync_status', String(20), default='idle'),
        Column('last_sync_time', DateTime(timezone=True), nullable=True),
        Column('backfill_completed_until', DateTime(timezone=True), nullable=True),
        Column('is_auto_syncing', Boolean, default=False),
        Column('error_message', String, nullable=True),
        Column('last_error_time', DateTime(timezone=True), nullable=True),
        Column('created_at', DateTime(timezone=True), nullable=False, server_default=func.now()),
        Column('updated_at', DateTime(timezone=True), nullable=False, server_default=func.now()),
    )

    return metadata


# Create engine once per session
_test_engine = None


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    global _test_engine
    _test_engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )

    # Create tables using test metadata
    metadata = get_test_metadata()
    async with _test_engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    yield _test_engine
    async with _test_engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
    await _test_engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh test database session for each test."""
    # Create a new session
    async_session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_factory() as session:
        # Clear all tables before each test
        await session.execute(text("DELETE FROM ohlcv"))
        await session.execute(text("DELETE FROM data_sync_state"))
        await session.execute(text("DELETE FROM api_keys"))
        await session.execute(text("DELETE FROM users"))
        await session.execute(text("DELETE FROM markets"))
        await session.commit()

        yield session

        # Rollback any uncommitted changes
        await session.rollback()


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.setex = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.ping = AsyncMock(return_value=True)
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def override_get_db(db_session):
    """Override FastAPI database dependency."""
    async def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(override_get_db, mock_redis) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing FastAPI endpoints."""
    # Patch redis_client globally
    with patch('app.core.redis.redis_client', mock_redis):
        with patch('app.api.v1.sync.redis_client', mock_redis):
            with patch('app.services.sync_state_service.redis_client', mock_redis):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    yield client


# Disable scheduler for tests
os.environ['SCHEDULER_ENABLED'] = 'false'