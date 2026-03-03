from sqlalchemy import Column, Integer, String, BigInteger, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(BigInteger, primary_key=True, index=True)
    client_order_id = Column(String(50), unique=True, index=True)
    exchange_order_id = Column(String, index=True)
    market_id = Column(Integer, ForeignKey("markets.id"))
    strategy_id = Column(Integer, ForeignKey("strategies.id"))
    account_id = Column(Integer, ForeignKey("accounts.id"), index=True)
    side = Column(String(4))
    type = Column(String(10))
    price = Column(Numeric(20, 10))
    amount = Column(Numeric(20, 10))
    filled = Column(Numeric(20, 10), default=0)
    remaining = Column(Numeric(20, 10))
    cost = Column(Numeric(20, 10), default=0)
    status = Column(String(20), index=True)
    created_at = Column(DateTime(timezone=True), index=True)
    updated_at = Column(DateTime(timezone=True))

    strategy = relationship("Strategy", back_populates="orders")
    account = relationship("Account", back_populates="orders")
    market = relationship("Market", back_populates="orders")
    executions = relationship("Execution", back_populates="order")


class Execution(Base):
    __tablename__ = "executions"

    id = Column(BigInteger, primary_key=True)
    order_id = Column(BigInteger, ForeignKey("orders.id"))
    trade_id = Column(String)
    price = Column(Numeric(20, 10), nullable=False)
    amount = Column(Numeric(20, 10), nullable=False)
    cost = Column(Numeric(20, 10))
    fee = Column(Numeric(20, 10))
    fee_currency = Column(String(10))
    time = Column(DateTime(timezone=True), index=True)
    taker_or_maker = Column(String(5))

    order = relationship("Order", back_populates="executions")
