"""Authentication dependencies for FastAPI."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.account import User, APIKey
from app.services.auth import decode_access_token
from app.services.user_service import UserService
from app.services.rate_limiter import rate_limiter


# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER, auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user from JWT token.

    Raises:
        HTTPException: If credentials are invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials:
        raise credentials_exception

    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise credentials_exception

    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    user_service = UserService(db)
    user = await user_service.get_user_by_username(username)

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure user is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Get current user if authenticated, otherwise return None.

    Use this for endpoints that have different behavior for authenticated vs anonymous users.
    """
    if not credentials:
        return None

    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        return None

    username: str = payload.get("sub")
    if username is None:
        return None

    user_service = UserService(db)
    user = await user_service.get_user_by_username(username)

    if user and user.is_active:
        return user

    return None


async def get_api_key_user(
    api_key: Optional[str] = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> tuple[User, APIKey]:
    """Authenticate via API key.

    Returns:
        Tuple of (User, APIKey) if valid

    Raises:
        HTTPException: If API key is invalid
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
        )

    user_service = UserService(db)
    api_key_obj = await user_service.verify_and_get_api_key(api_key)

    if not api_key_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
        )

    user = await user_service.get_user_by_id(api_key_obj.user_id)

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user, api_key_obj


async def get_authenticated_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    api_key: Optional[str] = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get authenticated user via either JWT token or API key.

    This is the main authentication dependency for protected endpoints.

    Raises:
        HTTPException: If neither authentication method is valid
    """
    # Try JWT token first
    if credentials:
        try:
            return await get_current_user(credentials, db)
        except HTTPException:
            pass

    # Try API key
    if api_key:
        user, _ = await get_api_key_user(api_key, db)
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required (Bearer token or API key)",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def check_rate_limit(
    api_key: Optional[str] = Depends(api_key_header),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Check rate limit for authenticated requests.

    This should be used as a dependency on endpoints that need rate limiting.
    """
    identifier = None
    rate_limit = settings.RATE_LIMIT_PER_MINUTE

    # Get identifier from API key or user
    if api_key:
        user_service = UserService(db)
        api_key_obj = await user_service.verify_and_get_api_key(api_key)
        if api_key_obj:
            identifier = f"apikey:{api_key_obj.id}"
            rate_limit = api_key_obj.rate_limit
    elif credentials:
        payload = decode_access_token(credentials.credentials)
        if payload and payload.get("sub"):
            user_service = UserService(db)
            user = await user_service.get_user_by_username(payload["sub"])
            if user:
                identifier = f"user:{user.id}"

    if identifier:
        allowed, rate_info = await rate_limiter.is_allowed(identifier, rate_limit)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(rate_info["limit"]),
                    "X-RateLimit-Remaining": str(rate_info["remaining"]),
                    "X-RateLimit-Reset": str(rate_info["reset"]),
                },
            )


def require_superuser(current_user: User = Depends(get_current_user)) -> User:
    """Require the current user to be a superuser."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required",
        )
    return current_user