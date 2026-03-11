"""Backtest engine for strategy testing.

This module provides the main backtest engine that orchestrates
strategy execution against historical data.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Generator
from collections import defaultdict

from app.strategy.base import (
    BaseStrategy,
    OHLCVBar,
)
from app.strategy.exchange_sim import ExchangeSimulator

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """Results of a backtest run."""
    # Basic info
    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float

    # Performance metrics
    total_return: float
    total_return_pct: float
    annualized_return: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    win_rate: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_trade_return: float

    # Detailed data
    trades: list[dict] = field(default_factory=list)
    equity_curve: list[tuple[datetime, float]] = field(default_factory=list)
    drawdown_curve: list[tuple[datetime, float]] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "strategy_name": self.strategy_name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "initial_capital": self.initial_capital,
            "final_capital": self.final_capital,
            "total_return": self.total_return,
            "total_return_pct": self.total_return_pct,
            "annualized_return": self.annualized_return,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_pct": self.max_drawdown_pct,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_trade_return": self.avg_trade_return,
        }


class PerformanceCalculator:
    """Calculate performance metrics from backtest results."""

    @staticmethod
    def calculate_returns(
        equity_curve: list[tuple[datetime, float]],
    ) -> list[float]:
        """Calculate periodic returns from equity curve."""
        if len(equity_curve) < 2:
            return []

        returns = []
        for i in range(1, len(equity_curve)):
            prev_equity = equity_curve[i - 1][1]
            curr_equity = equity_curve[i][1]
            if prev_equity > 0:
                returns.append((curr_equity - prev_equity) / prev_equity)
            else:
                returns.append(0.0)

        return returns

    @staticmethod
    def calculate_drawdown(
        equity_curve: list[tuple[datetime, float]],
    ) -> tuple[float, list[tuple[datetime, float]]]:
        """Calculate maximum drawdown and drawdown curve.

        Returns:
            Tuple of (max_drawdown_pct, drawdown_curve)
        """
        if not equity_curve:
            return 0.0, []

        peak = equity_curve[0][1]
        max_drawdown = 0.0
        drawdown_curve = []

        for time, equity in equity_curve:
            if equity > peak:
                peak = equity

            drawdown = 0.0
            if peak > 0:
                drawdown = (peak - equity) / peak * 100

            drawdown_curve.append((time, drawdown))
            max_drawdown = max(max_drawdown, drawdown)

        return max_drawdown, drawdown_curve

    @staticmethod
    def calculate_sharpe_ratio(
        returns: list[float],
        risk_free_rate: float = 0.02,
        periods_per_year: int = 252,
    ) -> float:
        """Calculate Sharpe ratio.

        Args:
            returns: List of periodic returns
            risk_free_rate: Annual risk-free rate (default 2%)
            periods_per_year: Number of periods per year

        Returns:
            Sharpe ratio
        """
        if not returns:
            return 0.0

        # Calculate mean and std of returns
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_return = variance ** 0.5

        if std_return == 0:
            return 0.0

        # Annualize
        annualized_mean = mean_return * periods_per_year
        annualized_std = std_return * (periods_per_year ** 0.5)

        # Calculate Sharpe
        excess_return = annualized_mean - risk_free_rate
        return excess_return / annualized_std if annualized_std > 0 else 0.0

    @staticmethod
    def calculate_sortino_ratio(
        returns: list[float],
        risk_free_rate: float = 0.02,
        periods_per_year: int = 252,
    ) -> float:
        """Calculate Sortino ratio (uses downside deviation).

        Args:
            returns: List of periodic returns
            risk_free_rate: Annual risk-free rate
            periods_per_year: Number of periods per year

        Returns:
            Sortino ratio
        """
        if not returns:
            return 0.0

        mean_return = sum(returns) / len(returns)

        # Calculate downside deviation
        negative_returns = [r for r in returns if r < 0]
        if not negative_returns:
            return float('inf')  # No negative returns

        downside_variance = sum(r ** 2 for r in negative_returns) / len(returns)
        downside_std = downside_variance ** 0.5

        if downside_std == 0:
            return 0.0

        # Annualize
        annualized_mean = mean_return * periods_per_year
        annualized_downside_std = downside_std * (periods_per_year ** 0.5)

        excess_return = annualized_mean - risk_free_rate
        return excess_return / annualized_downside_std if annualized_downside_std > 0 else 0.0

    @staticmethod
    def calculate_trade_statistics(
        trades: list[dict],
    ) -> tuple[float, float, int, int, int, float]:
        """Calculate trade-based statistics.

        Returns:
            Tuple of (win_rate, profit_factor, total_trades, winning_trades, losing_trades, avg_trade_return)
        """
        if not trades:
            return 0.0, 0.0, 0, 0, 0, 0.0

        # Separate winning and losing trades
        pnl_values = [t.get("pnl", 0) for t in trades if t.get("side") == "sell"]
        winning = [p for p in pnl_values if p > 0]
        losing = [p for p in pnl_values if p < 0]

        total_trades = len(pnl_values)
        winning_trades = len(winning)
        losing_trades = len(losing)

        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

        total_wins = sum(winning)
        total_losses = abs(sum(losing))
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

        avg_trade_return = sum(pnl_values) / len(pnl_values) if pnl_values else 0.0

        return win_rate, profit_factor, total_trades, winning_trades, losing_trades, avg_trade_return


class BacktestEngine:
    """Main backtest engine for running strategy simulations.

    Example:
        engine = BacktestEngine(
            strategy=MyStrategy(config),
            data_provider=my_data_provider,
        )
        result = await engine.run(start_date, end_date)
        print(result.to_dict())
    """

    def __init__(
        self,
        strategy: BaseStrategy,
        exchange: Optional[ExchangeSimulator] = None,
        commission_rate: float = 0.001,
        slippage_rate: float = 0.0005,
    ):
        self.strategy = strategy
        self.exchange = exchange or ExchangeSimulator(
            initial_capital=strategy.config.initial_capital,
            commission_rate=commission_rate,
            slippage_rate=slippage_rate,
        )

        # Data storage
        self._data: dict[str, list[OHLCVBar]] = defaultdict(list)
        self._current_idx: dict[str, int] = {}

    def load_data(
        self,
        symbol: str,
        bars: list[OHLCVBar],
    ) -> None:
        """Load historical data for a symbol.

        Args:
            symbol: Trading symbol
            bars: List of OHLCV bars (must be sorted by time)
        """
        self._data[symbol] = sorted(bars, key=lambda b: b.time)
        self._current_idx[symbol] = 0

    def load_data_from_dict(
        self,
        symbol: str,
        data: list[dict],
    ) -> None:
        """Load data from list of dictionaries.

        Args:
            symbol: Trading symbol
            data: List of dicts with keys: time, open, high, low, close, volume
        """
        bars = []
        for row in data:
            bar = OHLCVBar(
                time=row["time"] if isinstance(row["time"], datetime) else datetime.fromisoformat(row["time"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("volume", 0)),
            )
            bars.append(bar)

        self.load_data(symbol, bars)

    def _iterate_bars(self) -> Generator[tuple[datetime, str, OHLCVBar], None, None]:
        """Iterate through all bars in chronological order.

        Yields:
            Tuple of (time, symbol, bar)
        """
        # Combine all bars from all symbols
        all_bars = []
        for symbol, bars in self._data.items():
            for bar in bars:
                all_bars.append((bar.time, symbol, bar))

        # Sort by time
        all_bars.sort(key=lambda x: x[0])

        for time, symbol, bar in all_bars:
            yield time, symbol, bar

    def run(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> BacktestResult:
        """Run the backtest.

        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            BacktestResult with performance metrics
        """
        logger.info(f"Starting backtest for {self.strategy.config.name}")

        # Initialize strategy
        self.strategy.init()

        # Reset exchange
        self.exchange.reset()

        # Track equity curve
        equity_curve: list[tuple[datetime, float]] = []
        trade_records: list[dict] = []

        # Process each bar
        for time, symbol, bar in self._iterate_bars():
            # Filter by date range
            if start_date and bar.time < start_date:
                continue
            if end_date and bar.time > end_date:
                continue

            # Process the bar through the strategy
            signal = self.strategy.on_bar(bar, symbol)

            # Process any pending orders
            trades = self.exchange.process_bar(bar, symbol)

            # Process signal if generated
            if signal:
                self.exchange.process_signal(signal, bar.close)

            # Record trades
            for trade in trades:
                trade_records.append({
                    "order_id": trade.order_id,
                    "symbol": trade.symbol,
                    "side": trade.side.value,
                    "quantity": trade.quantity,
                    "price": trade.price,
                    "commission": trade.commission,
                    "executed_at": trade.executed_at.isoformat(),
                    "pnl": trade.pnl,
                })
                self.strategy.on_trade(trade_records[-1])

            # Update equity curve
            current_equity = self.exchange.total_equity
            equity_curve.append((bar.time, current_equity))
            self.strategy.state.equity_curve.append((bar.time, current_equity))

        # Finalize strategy
        self.strategy.on_finish()

        # Calculate performance metrics
        result = self._calculate_results(
            start_date=start_date or equity_curve[0][0] if equity_curve else datetime.now(),
            end_date=end_date or equity_curve[-1][0] if equity_curve else datetime.now(),
            equity_curve=equity_curve,
            trades=trade_records,
        )

        logger.info(
            f"Backtest completed: Return={result.total_return_pct:.2f}%, "
            f"Sharpe={result.sharpe_ratio:.2f}, MaxDD={result.max_drawdown_pct:.2f}%"
        )

        return result

    def _calculate_results(
        self,
        start_date: datetime,
        end_date: datetime,
        equity_curve: list[tuple[datetime, float]],
        trades: list[dict],
    ) -> BacktestResult:
        """Calculate backtest results and metrics."""
        initial_capital = self.strategy.config.initial_capital
        final_capital = equity_curve[-1][1] if equity_curve else initial_capital

        # Basic returns
        total_return = final_capital - initial_capital
        total_return_pct = (total_return / initial_capital) * 100 if initial_capital > 0 else 0

        # Annualized return
        days = (end_date - start_date).days
        years = days / 365 if days > 0 else 1
        annualized_return = ((final_capital / initial_capital) ** (1 / years) - 1) * 100 if years > 0 and initial_capital > 0 else 0

        # Drawdown
        max_drawdown, drawdown_curve = PerformanceCalculator.calculate_drawdown(equity_curve)

        # Returns for Sharpe/Sortino
        returns = PerformanceCalculator.calculate_returns(equity_curve)
        sharpe_ratio = PerformanceCalculator.calculate_sharpe_ratio(returns)
        sortino_ratio = PerformanceCalculator.calculate_sortino_ratio(returns)

        # Trade statistics
        win_rate, profit_factor, total_trades, winning_trades, losing_trades, avg_trade_return = \
            PerformanceCalculator.calculate_trade_statistics(trades)

        return BacktestResult(
            strategy_name=self.strategy.config.name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            total_return_pct=total_return_pct,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            avg_trade_return=avg_trade_return,
            trades=trades,
            equity_curve=equity_curve,
            drawdown_curve=drawdown_curve,
        )