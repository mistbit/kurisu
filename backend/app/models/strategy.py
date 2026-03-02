from sqlalchemy import Column, Integer, String, BigInteger, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    class_path = Column(String, nullable=False)
    parameters = Column(JSONB, default={})
    status = Column(String(20), default="active")
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))

    orders = relationship("Order", back_populates="strategy")


class StrategyRun(Base):
    __tablename__ = "strategy_runs"

    id = Column(BigInteger, primary_key=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"))
    type = Column(String(20))
    status = Column(String(20))
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True))
    parameters = Column(JSONB)
    metrics = Column(JSONB)


class RiskEvent(Base):
    __tablename__ = "risk_events"

    id = Column(BigInteger, primary_key=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"))
    market_id = Column(Integer, ForeignKey("markets.id"))
    account_id = Column(Integer, ForeignKey("accounts.id"))
    event_type = Column(String(50))
    severity = Column(String(20))
    details = Column(JSONB)
    created_at = Column(DateTime(timezone=True), index=True)
