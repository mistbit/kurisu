from sqlalchemy import Column, Integer, String, Boolean, Numeric, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class Market(Base):
    __tablename__ = "markets"

    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String(50), nullable=False)
    symbol = Column(String(50), nullable=False)
    base_asset = Column(String(20), nullable=False)
    quote_asset = Column(String(20), nullable=False)
    active = Column(Boolean, default=True)
    meta = Column(JSONB, default={})
    exchange_symbol = Column(String(50))
    price_precision = Column(Integer)
    amount_precision = Column(Integer)

    orders = relationship("Order", back_populates="market")

    __table_args__ = (
        UniqueConstraint('exchange', 'symbol', name='uix_exchange_symbol'),
    )


class OHLCV(Base):
    __tablename__ = "ohlcv"

    time = Column(DateTime(timezone=True), primary_key=True)
    market_id = Column(Integer, ForeignKey("markets.id"), primary_key=True)
    timeframe = Column(String(10), primary_key=True)
    open = Column(Numeric(20, 10), nullable=False)
    high = Column(Numeric(20, 10), nullable=False)
    low = Column(Numeric(20, 10), nullable=False)
    close = Column(Numeric(20, 10), nullable=False)
    volume = Column(Numeric(20, 10), nullable=False)


class Trade(Base):
    __tablename__ = "trades"

    time = Column(DateTime(timezone=True), primary_key=True)
    market_id = Column(Integer, ForeignKey("markets.id"), primary_key=True)
    trade_id = Column(String, nullable=False)
    side = Column(String(4))
    price = Column(Numeric(20, 10))
    amount = Column(Numeric(20, 10))
    cost = Column(Numeric(20, 10))
    taker_or_maker = Column(String(5))
