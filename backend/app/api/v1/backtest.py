import math
from datetime import date, datetime, time, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.market import Market
from app.services.exchange import ExchangeService
from app.strategy.backtest import BacktestEngine
from app.strategy.base import OHLCVBar
from app.strategy.examples import (
    MAStrategyConfig,
    MovingAverageCrossoverStrategy,
    RSIStrategy,
    RSIStrategyConfig,
)

router = APIRouter(prefix="/backtest", tags=["backtest"])

STRATEGIES = {
    "ma_crossover": MovingAverageCrossoverStrategy,
    "rsi": RSIStrategy,
}


class BacktestRequest(BaseModel):
    market_id: int | None = None
    symbol: str | None = None
    strategy: str
    start_date: str
    end_date: str
    initial_balance: float = 10000.0
    timeframe: str = "1h"
    fast_period: int = 10
    slow_period: int = 20
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0


class BacktestTrade(BaseModel):
    entry_time: int
    exit_time: int
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_percent: float


class BacktestResponse(BaseModel):
    initial_balance: float
    final_balance: float
    total_return: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    trades: list[BacktestTrade]
    equity_curve: list[float]


def _parse_request_datetime(value: str, *, end_of_day: bool) -> datetime:
    try:
        if "T" not in value:
            parsed_date = date.fromisoformat(value)
            boundary = time.max if end_of_day else time.min
            return datetime.combine(parsed_date, boundary, tzinfo=timezone.utc)

        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.") from exc

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _to_ms(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp() * 1000)


def _sanitize_number(value: float) -> float:
    numeric = float(value)
    return numeric if math.isfinite(numeric) else 0.0


def _build_strategy(request: BacktestRequest):
    if request.strategy == "ma_crossover":
        config = MAStrategyConfig(
            short_period=request.fast_period,
            long_period=request.slow_period,
            initial_capital=request.initial_balance,
        )
        return MovingAverageCrossoverStrategy(config)

    if request.strategy == "rsi":
        config = RSIStrategyConfig(
            rsi_period=request.rsi_period,
            oversold_threshold=request.rsi_oversold,
            overbought_threshold=request.rsi_overbought,
            initial_capital=request.initial_balance,
        )
        return RSIStrategy(config)

    raise HTTPException(status_code=400, detail=f"Unknown strategy: {request.strategy}")


async def _fetch_ohlcv_range(
    exchange_service: ExchangeService,
    symbol: str,
    timeframe: str,
    start_dt: datetime,
    end_dt: datetime,
    limit: int = 500,
) -> list[list[Any]]:
    since = _to_ms(start_dt)
    end_ms = _to_ms(end_dt)
    candles: list[list[Any]] = []

    while since <= end_ms:
        batch = await exchange_service.fetch_ohlcv(
            symbol,
            timeframe=timeframe,
            since=since,
            limit=limit,
        )
        if not batch:
            break

        for candle in batch:
            timestamp = int(candle[0])
            if timestamp > end_ms:
                return candles
            candles.append(candle)

        last_timestamp = int(batch[-1][0])
        if len(batch) < limit or last_timestamp >= end_ms:
            break

        next_since = last_timestamp + 1
        if next_since <= since:
            break
        since = next_since

    return candles


def _to_bar(candle: list[Any]) -> OHLCVBar:
    return OHLCVBar(
        time=datetime.fromtimestamp(int(candle[0]) / 1000, tz=timezone.utc),
        open=float(candle[1]),
        high=float(candle[2]),
        low=float(candle[3]),
        close=float(candle[4]),
        volume=float(candle[5]),
    )


def _build_trade_history(trades: list[dict[str, Any]]) -> list[BacktestTrade]:
    entries: dict[str, dict[str, Any]] = {}
    completed_trades: list[BacktestTrade] = []

    for trade in trades:
        symbol = str(trade["symbol"])
        side = str(trade["side"])
        if side == "buy":
            entries[symbol] = trade
            continue

        if side != "sell" or symbol not in entries:
            continue

        entry = entries.pop(symbol)
        entry_price = float(entry["price"])
        exit_price = float(trade["price"])
        quantity = float(trade["quantity"])
        pnl = _sanitize_number(trade.get("pnl") or 0.0)
        notional = entry_price * quantity
        pnl_percent = (pnl / notional) * 100 if notional > 0 else 0.0

        completed_trades.append(
            BacktestTrade(
                entry_time=_to_ms(datetime.fromisoformat(str(entry["executed_at"]))),
                exit_time=_to_ms(datetime.fromisoformat(str(trade["executed_at"]))),
                symbol=symbol,
                side="long",
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=quantity,
                pnl=pnl,
                pnl_percent=_sanitize_number(pnl_percent),
            )
        )

    return completed_trades


@router.post("/run", response_model=BacktestResponse)
async def run_backtest(
    request: BacktestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run a backtest for a given market."""
    start_dt = _parse_request_datetime(request.start_date, end_of_day=False)
    end_dt = _parse_request_datetime(request.end_date, end_of_day=True)
    if start_dt > end_dt:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")
    if request.market_id is None and not request.symbol:
        raise HTTPException(status_code=400, detail="market_id or symbol is required")

    strategy = _build_strategy(request)

    stmt = select(Market)
    if request.market_id is not None:
        stmt = stmt.where(Market.id == request.market_id)
    else:
        stmt = (
            stmt.where(Market.symbol == request.symbol)
            .order_by(Market.active.desc(), Market.id.asc())
        )

    result = await db.execute(stmt)
    market = result.scalars().first()

    if not market:
        market_lookup = request.market_id if request.market_id is not None else request.symbol
        raise HTTPException(status_code=404, detail=f"Market not found: {market_lookup}")

    exchange_service = ExchangeService(market.exchange)
    await exchange_service.initialize()

    try:
        ohlcv_rows = await _fetch_ohlcv_range(
            exchange_service,
            market.symbol,
            request.timeframe,
            start_dt,
            end_dt,
        )
    finally:
        await exchange_service.close()

    if not ohlcv_rows:
        raise HTTPException(status_code=404, detail="No data available for the specified period")

    engine = BacktestEngine(strategy=strategy)
    engine.load_data(market.symbol, [_to_bar(candle) for candle in ohlcv_rows])
    result_data = engine.run(start_dt, end_dt)
    completed_trades = _build_trade_history(result_data.trades)

    return BacktestResponse(
        initial_balance=_sanitize_number(result_data.initial_capital),
        final_balance=_sanitize_number(result_data.final_capital),
        total_return=_sanitize_number(result_data.total_return_pct),
        total_trades=result_data.total_trades,
        winning_trades=result_data.winning_trades,
        losing_trades=result_data.losing_trades,
        win_rate=_sanitize_number(result_data.win_rate * 100),
        profit_factor=_sanitize_number(result_data.profit_factor),
        sharpe_ratio=_sanitize_number(result_data.sharpe_ratio),
        sortino_ratio=_sanitize_number(result_data.sortino_ratio),
        max_drawdown=_sanitize_number(result_data.max_drawdown_pct),
        trades=completed_trades,
        equity_curve=[_sanitize_number(balance) for _, balance in result_data.equity_curve],
    )


@router.get("/strategies")
async def list_strategies():
    """List available backtest strategies."""
    return {"items": list(STRATEGIES.keys())}
