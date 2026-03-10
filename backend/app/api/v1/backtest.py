from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.strategy.backtest import BacktestEngine
from app.strategy.examples import MovingAverageCrossoverStrategy, RSIStrategy

router = APIRouter(prefix="/backtest", tags=["backtest"])

STRATEGIES = {
    "ma_crossover": MovingAverageCrossoverStrategy,
    "rsi": RSIStrategy,
}


class BacktestRequest(BaseModel):
    symbol: str
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


class BacktestResult(BaseModel):
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


@router.post("/run", response_model=BacktestResult)
async def run_backtest(
    request: BacktestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run a backtest for a given strategy and symbol."""
    if request.strategy not in STRATEGIES:
        raise HTTPException(status_code=400, detail=f"Unknown strategy: {request.strategy}")

    try:
        start_dt = datetime.fromisoformat(request.start_date)
        end_dt = datetime.fromisoformat(request.end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")

    # Get market from database
    from sqlalchemy import select
    from app.models.market import Market

    stmt = select(Market).where(Market.symbol == request.symbol)
    result = await db.execute(stmt)
    market = result.scalar_one_or_none()

    if not market:
        raise HTTPException(status_code=404, detail=f"Market not found: {request.symbol}")

    # Fetch OHLCV data
    from app.services.exchange import ExchangeService

    exchange_service = ExchangeService(market.exchange)
    await exchange_service.init()

    try:
        ohlcv_data = await exchange_service.fetch_ohlcv(
            market.symbol,
            request.timeframe,
            start_dt,
            end_dt,
        )
    finally:
        await exchange_service.close()

    if not ohlcv_data:
        raise HTTPException(status_code=404, detail="No data available for the specified period")

    # Create strategy instance
    strategy_class = STRATEGIES[request.strategy]
    params = {
        "fast_period": request.fast_period,
        "slow_period": request.slow_period,
        "rsi_period": request.rsi_period,
        "rsi_oversold": request.rsi_oversold,
        "rsi_overbought": request.rsi_overbought,
    }
    strategy = strategy_class(**params)

    # Run backtest
    engine = BacktestEngine(strategy=strategy, initial_balance=request.initial_balance)
    engine.load_data(market.symbol, ohlcv_data)
    result = engine.run(start_dt, end_dt)

    # Format response
    trades = [
        BacktestTrade(
            entry_time=t["entry_time"],
            exit_time=t["exit_time"],
            symbol=t["symbol"],
            side=t["side"],
            entry_price=t["entry_price"],
            exit_price=t["exit_price"],
            quantity=t["quantity"],
            pnl=t["pnl"],
            pnl_percent=t["pnl_percent"],
        )
        for t in result.get("trades", [])
    ]

    return BacktestResult(
        initial_balance=result["initial_balance"],
        final_balance=result["final_balance"],
        total_return=result["total_return"],
        total_trades=result["total_trades"],
        winning_trades=result["winning_trades"],
        losing_trades=result["losing_trades"],
        win_rate=result["win_rate"],
        profit_factor=result["profit_factor"],
        sharpe_ratio=result.get("sharpe_ratio", 0),
        sortino_ratio=result.get("sortino_ratio", 0),
        max_drawdown=result.get("max_drawdown", 0),
        trades=trades,
        equity_curve=result.get("equity_curve", []),
    )


@router.get("/strategies")
async def list_strategies():
    """List available backtest strategies."""
    return {"items": list(STRATEGIES.keys())}