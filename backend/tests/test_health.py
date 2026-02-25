import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock
from app.main import app
from app.core.database import get_db
from app.core.redis import redis_client

@pytest.mark.asyncio
async def test_health_check():
    # 1. Mock app.core.database.get_db
    mock_session = AsyncMock()
    # Mock execute to just return (awaitable)
    mock_session.execute.return_value = None 

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    # 2. Mock app.core.redis.redis_client.ping
    # Store original ping to restore later if needed (though not strictly necessary for a single test run)
    original_ping = redis_client.ping
    redis_client.ping = AsyncMock(return_value=True)

    try:
        # 3. Test GET /health
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/health")

        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "database": "connected",
            "redis": "connected"
        }
        
        # Verify mocks were called
        mock_session.execute.assert_called_once()
        redis_client.ping.assert_called_once()

    finally:
        # Cleanup
        app.dependency_overrides.clear()
        redis_client.ping = original_ping
