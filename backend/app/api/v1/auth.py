"""Authentication API routes."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import (
    get_current_user,
    get_authenticated_user,
    require_superuser,
    check_rate_limit,
)
from app.models.account import User, APIKey
from app.services.auth import create_access_token
from app.services.user_service import UserService


router = APIRouter(prefix="/auth", tags=["authentication"])


# ============ Pydantic Models ============


class UserCreate(BaseModel):
    """User registration request."""
    username: str
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """User response model."""
    id: int
    username: str
    email: str
    is_active: bool
    is_superuser: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginRequest(BaseModel):
    """Login request model."""
    username: str
    password: str


class APIKeyCreate(BaseModel):
    """API key creation request."""
    name: str
    rate_limit: int = 100
    expires_days: Optional[int] = None


class APIKeyResponse(BaseModel):
    """API key response model."""
    id: int
    name: str
    key: Optional[str] = None  # Only returned on creation
    is_active: bool
    rate_limit: int
    last_used_at: Optional[datetime] = None
    created_at: datetime
    expires_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PasswordChange(BaseModel):
    """Password change request."""
    current_password: str
    new_password: str


# ============ Endpoints ============


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user account.

    Note: In production, you may want to restrict registration or require email verification.
    """
    user_service = UserService(db)

    # Check if username exists
    if await user_service.get_user_by_username(request.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already registered",
        )

    # Check if email exists
    if await user_service.get_user_by_email(request.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create user
    user = await user_service.create_user(
        username=request.username,
        email=request.email,
        password=request.password,
    )
    await db.commit()

    return UserResponse.model_validate(user)


@router.post("/login", response_model=Token)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Login and get an access token."""
    user_service = UserService(db)
    user = await user_service.authenticate_user(request.username, request.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return Token(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_authenticated_user),
    _: None = Depends(check_rate_limit),
):
    """Get current authenticated user info."""
    return UserResponse.model_validate(current_user)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    request: PasswordChange,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Change current user's password."""
    user_service = UserService(db)

    # Verify current password
    if not await user_service.authenticate_user(current_user.username, request.current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Update password
    await user_service.update_password(current_user.id, request.new_password)
    await db.commit()


# ============ API Key Management ============


@router.post("/api-keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: APIKeyCreate,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new API key for the current user."""
    user_service = UserService(db)

    expires_at = None
    if request.expires_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=request.expires_days)

    api_key, plain_key = await user_service.create_api_key(
        user_id=current_user.id,
        name=request.name,
        rate_limit=request.rate_limit,
        expires_at=expires_at,
    )
    await db.commit()

    return APIKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key=plain_key,  # Only shown once
        is_active=api_key.is_active,
        rate_limit=api_key.rate_limit,
        last_used_at=api_key.last_used_at,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
    )


@router.get("/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """List all API keys for the current user."""
    user_service = UserService(db)
    api_keys = await user_service.list_user_api_keys(current_user.id)

    return [
        APIKeyResponse(
            id=ak.id,
            name=ak.name,
            key=None,  # Don't expose key hash
            is_active=ak.is_active,
            rate_limit=ak.rate_limit,
            last_used_at=ak.last_used_at,
            created_at=ak.created_at,
            expires_at=ak.expires_at,
        )
        for ak in api_keys
    ]


@router.delete("/api-keys/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    api_key_id: int,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke an API key."""
    user_service = UserService(db)
    api_keys = await user_service.list_user_api_keys(current_user.id)

    # Ensure the API key belongs to the current user
    if not any(ak.id == api_key_id for ak in api_keys):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    await user_service.revoke_api_key(api_key_id)
    await db.commit()


# ============ Admin Endpoints ============


@router.get("/admin/users", response_model=list[UserResponse])
async def list_users(
    _: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
):
    """List all users (admin only)."""
    from sqlalchemy import select

    result = await db.execute(select(User))
    users = result.scalars().all()

    return [UserResponse.model_validate(u) for u in users]


@router.delete("/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: int,
    _: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate a user account (admin only)."""
    user_service = UserService(db)
    user = await user_service.deactivate_user(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await db.commit()