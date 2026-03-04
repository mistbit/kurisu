from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    """User model for API authentication."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")


class APIKey(Base):
    """API key for programmatic access."""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    key_hash = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    rate_limit = Column(Integer, default=100)  # requests per minute
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="api_keys")


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    exchange = Column(String(50), nullable=False)
    meta = Column(JSONB, default={})

    orders = relationship("Order", back_populates="account")

    __table_args__ = (
        UniqueConstraint('exchange', 'name', name='uix_exchange_name'),
    )


class Balance(Base):
    __tablename__ = "balances"

    time = Column(DateTime(timezone=True), primary_key=True)
    asset = Column(String(20), primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), index=True)
    free = Column(Numeric(20, 10))
    used = Column(Numeric(20, 10))
    total = Column(Numeric(20, 10))


class Position(Base):
    __tablename__ = "positions"

    time = Column(DateTime(timezone=True), primary_key=True)
    market_id = Column(Integer, ForeignKey("markets.id"), primary_key=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"))
    account_id = Column(Integer, ForeignKey("accounts.id"), index=True)
    amount = Column(Numeric(20, 10))
    entry_price = Column(Numeric(20, 10))
    unrealized_pnl = Column(Numeric(20, 10))
