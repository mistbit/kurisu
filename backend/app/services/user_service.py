"""User management service."""
import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import User, APIKey
from app.services.auth import (
    get_password_hash,
    verify_password,
    generate_api_key,
    hash_api_key,
    verify_api_key,
)


class UserService:
    """Service for user and API key management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # User operations

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        is_superuser: bool = False,
    ) -> User:
        """Create a new user.

        Args:
            username: Unique username
            email: Unique email address
            password: Plain text password
            is_superuser: Whether user has superuser privileges

        Returns:
            Created User instance
        """
        hashed_password = get_password_hash(password)
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            is_superuser=is_superuser,
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def authenticate_user(
        self,
        username: str,
        password: str,
    ) -> Optional[User]:
        """Authenticate a user by username and password.

        Args:
            username: Username
            password: Plain text password

        Returns:
            User if authenticated, None otherwise
        """
        user = await self.get_user_by_username(username)
        if not user:
            return None
        if not user.is_active:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    async def update_password(
        self,
        user_id: int,
        new_password: str,
    ) -> Optional[User]:
        """Update user password."""
        user = await self.get_user_by_id(user_id)
        if user:
            user.hashed_password = get_password_hash(new_password)
            user.updated_at = datetime.now(timezone.utc)
            await self.db.flush()
        return user

    async def deactivate_user(self, user_id: int) -> Optional[User]:
        """Deactivate a user account."""
        user = await self.get_user_by_id(user_id)
        if user:
            user.is_active = False
            user.updated_at = datetime.now(timezone.utc)
            await self.db.flush()
        return user

    # API Key operations

    async def create_api_key(
        self,
        user_id: int,
        name: str,
        rate_limit: int = 100,
        expires_at: Optional[datetime] = None,
    ) -> tuple[APIKey, str]:
        """Create a new API key for a user.

        Args:
            user_id: User ID
            name: Human-readable name for the key
            rate_limit: Requests per minute limit
            expires_at: Optional expiration datetime

        Returns:
            Tuple of (APIKey instance, plain key string)
        """
        # Generate plain key
        plain_key = generate_api_key()
        key_hash = hash_api_key(plain_key)

        api_key = APIKey(
            user_id=user_id,
            key_hash=key_hash,
            name=name,
            rate_limit=rate_limit,
            expires_at=expires_at,
        )
        self.db.add(api_key)
        await self.db.flush()

        return api_key, plain_key

    async def get_api_key_by_hash(self, key_hash: str) -> Optional[APIKey]:
        """Get API key by hash (for internal lookup)."""
        result = await self.db.execute(
            select(APIKey).where(APIKey.key_hash == key_hash)
        )
        return result.scalar_one_or_none()

    async def verify_and_get_api_key(self, plain_key: str) -> Optional[APIKey]:
        """Verify an API key and return the instance if valid.

        Args:
            plain_key: Plain API key string

        Returns:
            APIKey if valid, None otherwise
        """
        # Get all active API keys and check against hash
        result = await self.db.execute(
            select(APIKey).where(APIKey.is_active == True)
        )
        api_keys = result.scalars().all()

        for api_key in api_keys:
            if verify_api_key(plain_key, api_key.key_hash):
                # Check expiration
                if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
                    return None

                # Update last used timestamp
                api_key.last_used_at = datetime.now(timezone.utc)
                await self.db.flush()

                return api_key

        return None

    async def list_user_api_keys(self, user_id: int) -> list[APIKey]:
        """List all API keys for a user."""
        result = await self.db.execute(
            select(APIKey).where(APIKey.user_id == user_id)
        )
        return list(result.scalars().all())

    async def revoke_api_key(self, api_key_id: int) -> Optional[APIKey]:
        """Revoke an API key."""
        result = await self.db.execute(
            select(APIKey).where(APIKey.id == api_key_id)
        )
        api_key = result.scalar_one_or_none()
        if api_key:
            api_key.is_active = False
            await self.db.flush()
        return api_key

    async def delete_api_key(self, api_key_id: int) -> bool:
        """Delete an API key permanently."""
        result = await self.db.execute(
            select(APIKey).where(APIKey.id == api_key_id)
        )
        api_key = result.scalar_one_or_none()
        if api_key:
            await self.db.delete(api_key)
            return True
        return False