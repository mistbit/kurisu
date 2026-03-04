"""Exchange simulator for backtesting.

This module provides a simulated exchange that executes orders
based on historical data.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from decimal import Decimal

from app.strategy.base import (
    Position,
    OrderSide,
    OrderType,
    Signal,
    SignalType,
    OHLCVBar,
)

logger = logging.getLogger(__name__)


@dataclass
class Order:
    """Order representation."""
    id: int
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None  # For limit orders
    stop_price: Optional[float] = None  # For stop orders
    created_at: datetime = field(default_factory=datetime.now)
    filled_at: Optional[datetime] = None
    filled_price: Optional[float] = None
    status: str = "pending"
    commission: float = 0.0


@dataclass
class Trade:
    """Executed trade representation."""
    order_id: int
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    commission: float
    executed_at: datetime
    pnl: Optional[float] = None


class ExchangeSimulator:
    """Simulated exchange for backtesting.

    Features:
    - Market and limit order execution
    - Stop-loss and take-profit handling
    - Commission calculation
    - Slippage simulation
    - Position tracking
    """

    def __init__(
        self,
        initial_capital: float = 10000.0,
        commission_rate: float = 0.001,  # 0.1% default
        slippage_rate: float = 0.0005,  # 0.05% default
        min_commission: float = 1.0,
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.min_commission = min_commission

        # State
        self.positions: dict[str, Position] = {}
        self.pending_orders: list[Order] = []
        self.trades: list[Trade] = []
        self._order_id_counter = 0

    @property
    def position_value(self) -> float:
        """Total value of open positions at entry price."""
        return sum(pos.quantity * pos.entry_price for pos in self.positions.values())

    @property
    def total_equity(self) -> float:
        """Total equity (cash + positions)."""
        return self.cash + self.position_value

    def _get_next_order_id(self) -> int:
        """Get next order ID."""
        self._order_id_counter += 1
        return self._order_id_counter

    def calculate_commission(self, value: float) -> float:
        """Calculate commission for a trade.

        Args:
            value: Trade value (price * quantity)

        Returns:
            Commission amount
        """
        return max(self.min_commission, value * self.commission_rate)

    def apply_slippage(self, price: float, side: OrderSide) -> float:
        """Apply slippage to execution price.

        Args:
            price: Original price
            side: Order side (buy/sell)

        Returns:
            Adjusted price with slippage
        """
        if side == OrderSide.BUY:
            return price * (1 + self.slippage_rate)
        else:
            return price * (1 - self.slippage_rate)

    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> Order:
        """Submit a new order.

        Args:
            symbol: Trading symbol
            side: Buy or sell
            quantity: Order quantity
            order_type: Market, limit, etc.
            price: Limit price (for limit orders)
            stop_price: Stop price (for stop orders)

        Returns:
            Created order
        """
        order = Order(
            id=self._get_next_order_id(),
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
        )

        self.pending_orders.append(order)
        logger.debug(f"Order submitted: {order.id} {side.value} {quantity} {symbol}")
        return order

    def process_signal(
        self,
        signal: Signal,
        current_price: float,
    ) -> Optional[Order]:
        """Process a trading signal and create an order.

        Args:
            signal: Trading signal
            current_price: Current market price

        Returns:
            Created order if any
        """
        symbol = signal.symbol

        if signal.type == SignalType.BUY:
            # Check if we already have a position
            if symbol in self.positions:
                logger.debug(f"Already have position in {symbol}, skipping buy")
                return None

            # Calculate quantity if not specified
            quantity = signal.quantity
            if quantity is None:
                quantity = (self.cash * 0.1) / current_price  # 10% of cash

            return self.submit_order(
                symbol=symbol,
                side=OrderSide.BUY,
                quantity=quantity,
                order_type=OrderType.MARKET if signal.price is None else OrderType.LIMIT,
                price=signal.price,
            )

        elif signal.type == SignalType.SELL:
            # Check if we have a position to sell
            if symbol not in self.positions:
                logger.debug(f"No position in {symbol}, skipping sell")
                return None

            position = self.positions[symbol]
            quantity = signal.quantity or position.quantity

            return self.submit_order(
                symbol=symbol,
                side=OrderSide.SELL,
                quantity=min(quantity, position.quantity),
                order_type=OrderType.MARKET if signal.price is None else OrderType.LIMIT,
                price=signal.price,
            )

        elif signal.type == SignalType.EXIT_LONG:
            # Exit long position
            if symbol in self.positions:
                position = self.positions[symbol]
                return self.submit_order(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    quantity=position.quantity,
                    order_type=OrderType.MARKET,
                )

        return None

    def process_bar(self, bar: OHLCVBar, symbol: str) -> list[Trade]:
        """Process a new bar and execute any pending orders.

        Args:
            bar: OHLCV bar data
            symbol: Symbol for this bar

        Returns:
            List of executed trades
        """
        executed_trades = []
        orders_to_remove = []

        for order in self.pending_orders:
            if order.symbol != symbol:
                continue

            executed = False
            fill_price = None

            if order.order_type == OrderType.MARKET:
                # Market orders execute at open price with slippage
                fill_price = self.apply_slippage(bar.open, order.side)
                executed = True

            elif order.order_type == OrderType.LIMIT:
                # Limit orders execute if price crosses limit
                if order.side == OrderSide.BUY and bar.low <= order.price:
                    fill_price = order.price
                    executed = True
                elif order.side == OrderSide.SELL and bar.high >= order.price:
                    fill_price = order.price
                    executed = True

            elif order.order_type == OrderType.STOP_LOSS:
                # Stop orders execute if price crosses stop
                if order.side == OrderSide.SELL and bar.low <= order.stop_price:
                    fill_price = self.apply_slippage(order.stop_price, order.side)
                    executed = True

            if executed and fill_price:
                trade = self._execute_order(order, fill_price, bar.time)
                executed_trades.append(trade)
                orders_to_remove.append(order)

        # Remove executed orders
        for order in orders_to_remove:
            self.pending_orders.remove(order)

        # Check stop-loss and take-profit for open positions
        if symbol in self.positions:
            self._check_position_exits(bar, symbol, executed_trades)

        return executed_trades

    def _execute_order(
        self,
        order: Order,
        fill_price: float,
        fill_time: datetime,
    ) -> Trade:
        """Execute an order and update positions.

        Args:
            order: Order to execute
            fill_price: Execution price
            fill_time: Execution time

        Returns:
            Executed trade
        """
        trade_value = fill_price * order.quantity
        commission = self.calculate_commission(trade_value)

        order.status = "filled"
        order.filled_at = fill_time
        order.filled_price = fill_price
        order.commission = commission

        pnl = None
        symbol = order.symbol

        if order.side == OrderSide.BUY:
            # Deduct cash
            self.cash -= (trade_value + commission)

            # Create or update position
            if symbol in self.positions:
                # Add to existing position
                pos = self.positions[symbol]
                total_quantity = pos.quantity + order.quantity
                avg_price = (pos.entry_price * pos.quantity + fill_price * order.quantity) / total_quantity
                pos.quantity = total_quantity
                pos.entry_price = avg_price
            else:
                # New position
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=order.quantity,
                    entry_price=fill_price,
                    entry_time=fill_time,
                    side=OrderSide.BUY,
                )

        else:  # SELL
            # Add cash
            self.cash += (trade_value - commission)

            # Calculate PnL if closing a position
            if symbol in self.positions:
                pos = self.positions[symbol]
                pnl = (fill_price - pos.entry_price) * order.quantity - commission

                # Update or close position
                if order.quantity >= pos.quantity:
                    del self.positions[symbol]
                else:
                    pos.quantity -= order.quantity

        trade = Trade(
            order_id=order.id,
            symbol=symbol,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
            commission=commission,
            executed_at=fill_time,
            pnl=pnl,
        )

        self.trades.append(trade)
        logger.debug(
            f"Trade executed: {order.side.value} {order.quantity} {symbol} @ {fill_price}, "
            f"PnL: {pnl}, Commission: {commission}"
        )

        return trade

    def _check_position_exits(
        self,
        bar: OHLCVBar,
        symbol: str,
        executed_trades: list[Trade],
    ) -> None:
        """Check and execute stop-loss and take-profit orders.

        Args:
            bar: Current OHLCV bar
            symbol: Symbol for this bar
            executed_trades: List to append executed trades to
        """
        if symbol not in self.positions:
            return

        position = self.positions[symbol]

        # Check stop-loss
        if position.stop_loss and bar.low <= position.stop_loss:
            fill_price = self.apply_slippage(position.stop_loss, OrderSide.SELL)
            order = self.submit_order(
                symbol=symbol,
                side=OrderSide.SELL,
                quantity=position.quantity,
                order_type=OrderType.STOP_LOSS,
                stop_price=position.stop_loss,
            )
            # Execute immediately
            if order in self.pending_orders:
                trade = self._execute_order(order, fill_price, bar.time)
                executed_trades.append(trade)
                self.pending_orders.remove(order)

        # Check take-profit
        elif position.take_profit and bar.high >= position.take_profit:
            fill_price = position.take_profit
            order = self.submit_order(
                symbol=symbol,
                side=OrderSide.SELL,
                quantity=position.quantity,
                order_type=OrderType.LIMIT,
                price=position.take_profit,
            )
            if order in self.pending_orders:
                trade = self._execute_order(order, fill_price, bar.time)
                executed_trades.append(trade)
                self.pending_orders.remove(order)

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get current position for a symbol."""
        return self.positions.get(symbol)

    def get_all_positions(self) -> dict[str, Position]:
        """Get all current positions."""
        return self.positions.copy()

    def get_trade_history(self) -> list[Trade]:
        """Get trade history."""
        return self.trades.copy()

    def reset(self) -> None:
        """Reset the exchange to initial state."""
        self.cash = self.initial_capital
        self.positions.clear()
        self.pending_orders.clear()
        self.trades.clear()
        self._order_id_counter = 0