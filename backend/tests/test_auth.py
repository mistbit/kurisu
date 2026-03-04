"""Tests for authentication API endpoints."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import User, APIKey
from app.services.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token,
    generate_api_key,
)
from app.services.user_service import UserService


@pytest.mark.asyncio
async def test_password_hashing():
    """Test password hashing and verification."""
    password = "test_password_123"
    hashed = get_password_hash(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong_password", hashed)


@pytest.mark.asyncio
async def test_create_and_decode_access_token():
    """Test JWT token creation and decoding."""
    data = {"sub": "testuser"}
    token = create_access_token(data)

    assert token is not None
    assert isinstance(token, str)

    # Decode the token
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "testuser"


@pytest.mark.asyncio
async def test_decode_invalid_token():
    """Test decoding an invalid token."""
    payload = decode_access_token("invalid_token")
    assert payload is None


@pytest.mark.asyncio
async def test_generate_api_key():
    """Test API key generation."""
    key = generate_api_key()

    assert key is not None
    assert isinstance(key, str)
    assert len(key) == 64  # 32 bytes hex = 64 characters


@pytest.mark.asyncio
async def test_create_user(db_session: AsyncSession):
    """Test user creation."""
    user_service = UserService(db_session)

    user = await user_service.create_user(
        username="testuser",
        email="test@example.com",
        password="password123",
    )
    await db_session.commit()

    assert user.id is not None
    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.is_active is True
    assert user.is_superuser is False


@pytest.mark.asyncio
async def test_create_duplicate_user(db_session: AsyncSession):
    """Test that duplicate usernames are rejected."""
    user_service = UserService(db_session)

    # Create first user
    await user_service.create_user(
        username="testuser",
        email="test1@example.com",
        password="password123",
    )
    await db_session.commit()

    # Try to create duplicate
    with pytest.raises(Exception):  # Will raise IntegrityError
        await user_service.create_user(
            username="testuser",
            email="test2@example.com",
            password="password456",
        )
        await db_session.commit()


@pytest.mark.asyncio
async def test_authenticate_user(db_session: AsyncSession):
    """Test user authentication."""
    user_service = UserService(db_session)

    # Create user
    await user_service.create_user(
        username="testuser",
        email="test@example.com",
        password="password123",
    )
    await db_session.commit()

    # Authenticate with correct password
    user = await user_service.authenticate_user("testuser", "password123")
    assert user is not None
    assert user.username == "testuser"

    # Authenticate with wrong password
    user = await user_service.authenticate_user("testuser", "wrongpassword")
    assert user is None

    # Authenticate with non-existent user
    user = await user_service.authenticate_user("nonexistent", "password123")
    assert user is None


@pytest.mark.asyncio
async def test_create_api_key(db_session: AsyncSession):
    """Test API key creation."""
    user_service = UserService(db_session)

    # Create user first
    user = await user_service.create_user(
        username="testuser",
        email="test@example.com",
        password="password123",
    )
    await db_session.commit()

    # Create API key
    api_key, plain_key = await user_service.create_api_key(
        user_id=user.id,
        name="Test Key",
        rate_limit=50,
    )
    await db_session.commit()

    assert api_key.id is not None
    assert api_key.name == "Test Key"
    assert api_key.rate_limit == 50
    assert plain_key is not None
    assert len(plain_key) == 64


@pytest.mark.asyncio
async def test_verify_api_key(db_session: AsyncSession):
    """Test API key verification."""
    user_service = UserService(db_session)

    # Create user and API key
    user = await user_service.create_user(
        username="testuser",
        email="test@example.com",
        password="password123",
    )
    await db_session.commit()

    api_key, plain_key = await user_service.create_api_key(
        user_id=user.id,
        name="Test Key",
    )
    await db_session.commit()

    # Verify the key
    verified_key = await user_service.verify_and_get_api_key(plain_key)
    assert verified_key is not None
    assert verified_key.id == api_key.id

    # Verify wrong key
    verified_key = await user_service.verify_and_get_api_key("wrong_key")
    assert verified_key is None


@pytest.mark.asyncio
async def test_revoke_api_key(db_session: AsyncSession):
    """Test API key revocation."""
    user_service = UserService(db_session)

    # Create user and API key
    user = await user_service.create_user(
        username="testuser",
        email="test@example.com",
        password="password123",
    )
    await db_session.commit()

    api_key, plain_key = await user_service.create_api_key(
        user_id=user.id,
        name="Test Key",
    )
    await db_session.commit()

    # Verify key works
    verified = await user_service.verify_and_get_api_key(plain_key)
    assert verified is not None

    # Revoke the key
    await user_service.revoke_api_key(api_key.id)
    await db_session.commit()

    # Verify key no longer works
    verified = await user_service.verify_and_get_api_key(plain_key)
    assert verified is None


# ============ API Endpoint Tests ============


@pytest.mark.asyncio
async def test_register_endpoint(async_client: AsyncClient):
    """Test user registration endpoint."""
    response = await async_client.post(
        "/api/v1/auth/register",
        json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "newuser@example.com"


@pytest.mark.asyncio
async def test_register_duplicate_username(async_client: AsyncClient, db_session: AsyncSession):
    """Test registration with duplicate username."""
    user_service = UserService(db_session)
    await user_service.create_user(
        username="existinguser",
        email="existing@example.com",
        password="password123",
    )
    await db_session.commit()

    response = await async_client.post(
        "/api/v1/auth/register",
        json={
            "username": "existinguser",
            "email": "new@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_endpoint(async_client: AsyncClient, db_session: AsyncSession):
    """Test login endpoint."""
    user_service = UserService(db_session)
    await user_service.create_user(
        username="loginuser",
        email="login@example.com",
        password="password123",
    )
    await db_session.commit()

    response = await async_client.post(
        "/api/v1/auth/login",
        json={
            "username": "loginuser",
            "password": "password123",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(async_client: AsyncClient, db_session: AsyncSession):
    """Test login with wrong password."""
    user_service = UserService(db_session)
    await user_service.create_user(
        username="loginuser",
        email="login@example.com",
        password="password123",
    )
    await db_session.commit()

    response = await async_client.post(
        "/api/v1/auth/login",
        json={
            "username": "loginuser",
            "password": "wrongpassword",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_unauthenticated(async_client: AsyncClient):
    """Test getting current user info without authentication."""
    response = await async_client.get("/api/v1/auth/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_with_token(async_client: AsyncClient, db_session: AsyncSession):
    """Test getting current user info with valid token."""
    user_service = UserService(db_session)
    user = await user_service.create_user(
        username="meuser",
        email="me@example.com",
        password="password123",
    )
    await db_session.commit()

    # Create token
    token = create_access_token(data={"sub": "meuser"})

    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "meuser"


@pytest.mark.asyncio
async def test_create_api_key_endpoint(async_client: AsyncClient, db_session: AsyncSession):
    """Test API key creation endpoint."""
    user_service = UserService(db_session)
    user = await user_service.create_user(
        username="apikeyuser",
        email="apikey@example.com",
        password="password123",
    )
    await db_session.commit()

    token = create_access_token(data={"sub": "apikeyuser"})

    response = await async_client.post(
        "/api/v1/auth/api-keys",
        json={"name": "Test Key", "rate_limit": 50},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Key"
    assert data["key"] is not None  # Plain key shown on creation


@pytest.mark.asyncio
async def test_list_api_keys(async_client: AsyncClient, db_session: AsyncSession):
    """Test listing API keys endpoint."""
    user_service = UserService(db_session)
    user = await user_service.create_user(
        username="listkeysuser",
        email="listkeys@example.com",
        password="password123",
    )
    await db_session.commit()

    # Create two API keys
    await user_service.create_api_key(user_id=user.id, name="Key 1")
    await user_service.create_api_key(user_id=user.id, name="Key 2")
    await db_session.commit()

    token = create_access_token(data={"sub": "listkeysuser"})

    response = await async_client.get(
        "/api/v1/auth/api-keys",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Key should not be exposed in list
    assert all(k["key"] is None for k in data)