from datetime import datetime, timezone
from typing import Optional, Dict, Any, Sequence

import ccxt.async_support as ccxt
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market import Market, OHLCV

class ExchangeService:
    def __init__(self, exchange_id: str, config: Optional[Dict[str, Any]] = None):
        self.exchange_id = exchange_id
        self.config = {"enableRateLimit": True, **(config or {})}
        self._exchange: Optional[ccxt.Exchange] = None

    async def initialize(self):
        if self.exchange_id not in ccxt.exchanges:
            raise ValueError(f"Exchange {self.exchange_id} not supported by ccxt")

        exchange_class = getattr(ccxt, self.exchange_id)
        self._exchange = exchange_class(self.config)

    async def close(self):
        if self._exchange:
            await self._exchange.close()

    async def load_markets(self) -> Dict[str, Any]:
        if not self._exchange:
            await self.initialize()
        return await self._exchange.load_markets()

    async def fetch_markets(self) -> Dict[str, Any]:
        return await self.load_markets()

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        if not self._exchange:
            await self.initialize()
        return await self._exchange.fetch_ticker(symbol)

    async def fetch_balance(self) -> Dict[str, Any]:
        if not self._exchange:
            await self.initialize()
        return await self._exchange.fetch_balance()

    async def fetch_ohlcv(
        self, symbol: str, timeframe: str, since: Optional[int] = None, limit: Optional[int] = None
    ) -> list[list[Any]]:
        if not self._exchange:
            await self.initialize()
        return await self._exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)

    @property
    def exchange(self) -> ccxt.Exchange:
        if not self._exchange:
            raise RuntimeError("Exchange not initialized. Call initialize() first.")
        return self._exchange


class MarketService:
    def __init__(self, exchange_service: ExchangeService, session: AsyncSession):
        self.exchange_service = exchange_service
        self.session = session

    async def sync_markets(
        self,
        quote_allowlist: Optional[Sequence[str]] = None,
        quote_denylist: Optional[Sequence[str]] = None,
    ) -> int:
        markets = await self.exchange_service.fetch_markets()
        rows = []
        for market in markets.values():
            quote_asset = market.get("quote")
            if quote_allowlist and quote_asset not in quote_allowlist:
                continue
            if quote_denylist and quote_asset in quote_denylist:
                continue
            symbol = market.get("symbol") or market.get("id")
            if not symbol:
                continue
            precision = market.get("precision") or {}
            rows.append(
                {
                    "exchange": self.exchange_service.exchange_id,
                    "symbol": symbol,
                    "base_asset": market.get("base"),
                    "quote_asset": quote_asset,
                    "active": market.get("active", True),
                    "meta": market,
                    "exchange_symbol": market.get("id"),
                    "price_precision": _parse_precision(precision.get("price")),
                    "amount_precision": _parse_precision(precision.get("amount")),
                }
            )
        if not rows:
            return 0
        stmt = insert(Market).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["exchange", "symbol"],
            set_={
                "base_asset": stmt.excluded.base_asset,
                "quote_asset": stmt.excluded.quote_asset,
                "active": stmt.excluded.active,
                "meta": stmt.excluded.meta,
                "exchange_symbol": stmt.excluded.exchange_symbol,
                "price_precision": stmt.excluded.price_precision,
                "amount_precision": stmt.excluded.amount_precision,
            },
        )
        await self.session.execute(stmt)
        await self.session.commit()
        return len(rows)


class MarketDataService:
    def __init__(self, exchange_service: ExchangeService, session: AsyncSession):
        self.exchange_service = exchange_service
        self.session = session

    async def fetch_ohlcv_history(
        self,
        symbol: str,
        market_id: int,
        timeframe: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        limit: int = 500,
    ) -> int:
        since = _to_ms(start_time)
        end_ms = _to_ms(end_time) if end_time else None
        total_rows = 0
        while True:
            batch = await self.exchange_service.fetch_ohlcv(
                symbol=symbol, timeframe=timeframe, since=since, limit=limit
            )
            if not batch:
                break
            rows = []
            for ts, open_price, high, low, close, volume in batch:
                if end_ms is not None and ts > end_ms:
                    break
                rows.append(
                    {
                        "time": _to_datetime(ts),
                        "market_id": market_id,
                        "timeframe": timeframe,
                        "open": open_price,
                        "high": high,
                        "low": low,
                        "close": close,
                        "volume": volume,
                    }
                )
            if rows:
                await self._upsert_ohlcv(rows)
                total_rows += len(rows)
            last_ts = batch[-1][0]
            since = last_ts + 1
            if end_ms is not None and since > end_ms:
                break
            if len(batch) < limit:
                break
        return total_rows

    async def _upsert_ohlcv(self, rows: list[dict[str, Any]]) -> None:
        stmt = insert(OHLCV).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["time", "market_id", "timeframe"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
            },
        )
        await self.session.execute(stmt)
        await self.session.commit()


def _to_datetime(timestamp_ms: int) -> datetime:
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)


def _to_ms(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp() * 1000)


def _parse_precision(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    return None
