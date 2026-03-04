"""Simple Moving Average Crossover Strategy.

This strategy generates buy signals when the short MA crosses above the long MA,
and sell signals when it crosses below.
"""
from typing import Optional
from datetime import datetime

from app.strategy.base import (
    BaseStrategy,
    StrategyConfig,
    OHLCVBar,
    Signal,
    SignalType,
)


class MAStrategyConfig(StrategyConfig):
    """Configuration for MA Crossover strategy."""
    name: str = "MA_Crossover"
    short_period: int = 10
    long_period: int = 20


class MovingAverageCrossoverStrategy(BaseStrategy):
    """Simple Moving Average Crossover Strategy.

    Buy when short MA crosses above long MA.
    Sell when short MA crosses below long MA.
    """

    def __init__(self, config: Optional[MAStrategyConfig] = None):
        super().__init__(config or MAStrategyConfig())
        self._prev_short_ma: dict[str, float] = {}
        self._prev_long_ma: dict[str, float] = {}

    def init(self) -> None:
        """Initialize the strategy."""
        self._prev_short_ma = {}
        self._prev_long_ma = {}

    def generate_signal(self, bar: OHLCVBar, symbol: str) -> Optional[Signal]:
        """Generate trading signal based on MA crossover.

        Args:
            bar: Current OHLCV bar
            symbol: Symbol being processed

        Returns:
            Signal if crossover occurs, None otherwise
        """
        config = self.config  # type: MAStrategyConfig
        short_period = config.short_period
        long_period = config.long_period

        # Get close prices
        close_prices = self.get_close_prices(symbol, long_period + 1)

        if len(close_prices) < long_period:
            return None

        # Calculate MAs
        short_ma = sum(close_prices[-short_period:]) / short_period
        long_ma = sum(close_prices[-long_period:]) / long_period

        # Get previous MAs
        prev_short = self._prev_short_ma.get(symbol)
        prev_long = self._prev_long_ma.get(symbol)

        # Store current MAs for next iteration
        self._prev_short_ma[symbol] = short_ma
        self._prev_long_ma[symbol] = long_ma

        if prev_short is None or prev_long is None:
            return None

        # Check for crossover
        # Bullish crossover: short MA crosses above long MA
        if prev_short <= prev_long and short_ma > long_ma:
            if not self.has_position(symbol):
                return Signal(
                    type=SignalType.BUY,
                    symbol=symbol,
                    time=bar.time,
                    metadata={
                        "short_ma": short_ma,
                        "long_ma": long_ma,
                        "reason": "bullish_crossover",
                    }
                )

        # Bearish crossover: short MA crosses below long MA
        elif prev_short >= prev_long and short_ma < long_ma:
            if self.has_position(symbol):
                return Signal(
                    type=SignalType.SELL,
                    symbol=symbol,
                    time=bar.time,
                    metadata={
                        "short_ma": short_ma,
                        "long_ma": long_ma,
                        "reason": "bearish_crossover",
                    }
                )

        return None


class RSIStrategyConfig(StrategyConfig):
    """Configuration for RSI strategy."""
    name: str = "RSI_Strategy"
    rsi_period: int = 14
    oversold_threshold: float = 30.0
    overbought_threshold: float = 70.0


class RSIStrategy(BaseStrategy):
    """RSI Mean Reversion Strategy.

    Buy when RSI is oversold (< oversold_threshold).
    Sell when RSI is overbought (> overbought_threshold).
    """

    def __init__(self, config: Optional[RSIStrategyConfig] = None):
        super().__init__(config or RSIStrategyConfig())
        self._rsi_values: dict[str, list[float]] = {}

    def _calculate_rsi(self, prices: list[float], period: int) -> Optional[float]:
        """Calculate RSI value.

        Args:
            prices: List of prices
            period: RSI period

        Returns:
            RSI value or None if not enough data
        """
        if len(prices) < period + 1:
            return None

        # Calculate price changes
        changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

        # Separate gains and losses
        gains = [max(0, c) for c in changes]
        losses = [abs(min(0, c)) for c in changes]

        # Calculate average gain and loss
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def generate_signal(self, bar: OHLCVBar, symbol: str) -> Optional[Signal]:
        """Generate trading signal based on RSI.

        Args:
            bar: Current OHLCV bar
            symbol: Symbol being processed

        Returns:
            Signal if RSI crosses threshold, None otherwise
        """
        config = self.config  # type: RSIStrategyConfig
        period = config.rsi_period

        # Get close prices
        close_prices = self.get_close_prices(symbol, period + 2)

        if len(close_prices) < period + 1:
            return None

        # Calculate RSI
        rsi = self._calculate_rsi(close_prices, period)
        if rsi is None:
            return None

        # Store RSI value
        if symbol not in self._rsi_values:
            self._rsi_values[symbol] = []
        self._rsi_values[symbol].append(rsi)

        # Check thresholds
        # Buy when RSI is oversold
        if rsi < config.oversold_threshold:
            if not self.has_position(symbol):
                return Signal(
                    type=SignalType.BUY,
                    symbol=symbol,
                    time=bar.time,
                    metadata={
                        "rsi": rsi,
                        "reason": "oversold",
                    }
                )

        # Sell when RSI is overbought
        elif rsi > config.overbought_threshold:
            if self.has_position(symbol):
                return Signal(
                    type=SignalType.SELL,
                    symbol=symbol,
                    time=bar.time,
                    metadata={
                        "rsi": rsi,
                        "reason": "overbought",
                    }
                )

        return None