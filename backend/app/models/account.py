from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


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
