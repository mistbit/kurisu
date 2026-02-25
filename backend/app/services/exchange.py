import ccxt.async_support as ccxt
from typing import Optional, Dict, Any

class ExchangeService:
    def __init__(self, exchange_id: str, config: Optional[Dict[str, Any]] = None):
        self.exchange_id = exchange_id
        self.config = config or {}
        self._exchange: Optional[ccxt.Exchange] = None

    async def initialize(self):
        """Initialize the exchange instance."""
        if self.exchange_id not in ccxt.exchanges:
            raise ValueError(f"Exchange {self.exchange_id} not supported by ccxt")
        
        exchange_class = getattr(ccxt, self.exchange_id)
        self._exchange = exchange_class(self.config)
        # Load markets to verify connection and get market data
        # await self._exchange.load_markets()

    async def close(self):
        """Close the exchange connection."""
        if self._exchange:
            await self._exchange.close()

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch ticker for a symbol."""
        if not self._exchange:
            await self.initialize()
        return await self._exchange.fetch_ticker(symbol)

    async def fetch_balance(self) -> Dict[str, Any]:
        """Fetch account balance."""
        if not self._exchange:
            await self.initialize()
        return await self._exchange.fetch_balance()
    
    @property
    def exchange(self) -> ccxt.Exchange:
        """Get the underlying ccxt exchange instance."""
        if not self._exchange:
             raise RuntimeError("Exchange not initialized. Call initialize() first.")
        return self._exchange
