"""Real-time OHLCV data streaming service."""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.market import Market, OHLCV
from app.services.exchange import ExchangeService
from app.api.v1.websocket import manager as ws_manager

logger = logging.getLogger(__name__)


class OHLCVStreamService:
    """Service for streaming real-time OHLCV data to WebSocket clients.

    This service polls exchange APIs for the latest OHLCV data and
    broadcasts it to subscribed WebSocket clients.

    Future enhancement: Upgrade to use exchange WebSocket APIs for
    lower latency instead of polling.
    """

    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None
        self._exchange_services: dict[str, ExchangeService] = {}
        self._poll_interval = 5  # seconds

    async def start(self) -> None:
        """Start the streaming service."""
        if self._running:
            logger.warning("OHLCV stream service already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._stream_loop())
        logger.info("OHLCV stream service started")

    async def stop(self) -> None:
        """Stop the streaming service."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        # Close all exchange services
        for exchange, service in self._exchange_services.items():
            try:
                await service.close()
            except Exception as e:
                logger.error(f"Error closing exchange service {exchange}: {e}")
        self._exchange_services.clear()

        logger.info("OHLCV stream service stopped")

    async def _stream_loop(self) -> None:
        """Main streaming loop."""
        while self._running:
            try:
                await self._poll_and_broadcast()
            except Exception as e:
                logger.error(f"Error in stream loop: {e}")

            await asyncio.sleep(self._poll_interval)

    async def _poll_and_broadcast(self) -> None:
        """Poll exchanges for latest data and broadcast to subscribers."""
        # Get all active subscriptions
        stats = ws_manager.get_stats()
        subscriptions = stats.get("subscription_details", {})

        if not subscriptions:
            return

        async with SessionLocal() as session:
            for sub_key, subscriber_count in subscriptions.items():
                try:
                    market_id, timeframe = sub_key.split(":")

                    # Get market info
                    result = await session.execute(
                        select(Market).where(Market.id == int(market_id))
                    )
                    market = result.scalar_one_or_none()

                    if not market:
                        continue

                    # Get latest OHLCV from exchange
                    ohlcv_data = await self._fetch_latest_ohlcv(
                        market.exchange,
                        market.symbol,
                        timeframe,
                    )

                    if ohlcv_data:
                        # Broadcast to subscribers
                        await ws_manager.broadcast(
                            int(market_id),
                            timeframe,
                            {
                                "type": "ohlcv_update",
                                "market_id": int(market_id),
                                "symbol": market.symbol,
                                "timeframe": timeframe,
                                "data": ohlcv_data,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }
                        )

                        # Also store in database
                        await self._store_ohlcv(session, int(market_id), timeframe, ohlcv_data)

                except Exception as e:
                    logger.error(f"Error processing subscription {sub_key}: {e}")

    async def _fetch_latest_ohlcv(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
    ) -> list | None:
        """Fetch the latest OHLCV candle from exchange.

        Args:
            exchange: Exchange ID (e.g., "binance")
            symbol: Trading pair symbol (e.g., "BTC/USDT")
            timeframe: Timeframe (e.g., "1h", "4h", "1d")

        Returns:
            OHLCV data as [timestamp_ms, open, high, low, close, volume] or None
        """
        try:
            # Get or create exchange service
            if exchange not in self._exchange_services:
                service = ExchangeService(exchange)
                await service.initialize()
                self._exchange_services[exchange] = service

            service = self._exchange_services[exchange]

            # Fetch latest candle
            ohlcv_list = await service.fetch_ohlcv(symbol, timeframe, limit=1)

            if ohlcv_list and len(ohlcv_list) > 0:
                return ohlcv_list[0]  # [timestamp_ms, open, high, low, close, volume]

            return None

        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol}/{timeframe}: {e}")
            return None

    async def _store_ohlcv(
        self,
        session,
        market_id: int,
        timeframe: str,
        ohlcv_data: list,
    ) -> None:
        """Store OHLCV data in database.

        Args:
            session: Database session
            market_id: Market ID
            timeframe: Timeframe
            ohlcv_data: [timestamp_ms, open, high, low, close, volume]
        """
        try:
            timestamp_ms, open_price, high, low, close, volume = ohlcv_data
            time = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

            # Check if candle already exists
            result = await session.execute(
                select(OHLCV).where(
                    OHLCV.time == time,
                    OHLCV.market_id == market_id,
                    OHLCV.timeframe == timeframe,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing candle (might be partially filled)
                existing.open = open_price
                existing.high = high
                existing.low = low
                existing.close = close
                existing.volume = volume
            else:
                # Create new candle
                candle = OHLCV(
                    time=time,
                    market_id=market_id,
                    timeframe=timeframe,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
                session.add(candle)

            await session.commit()

        except Exception as e:
            logger.error(f"Error storing OHLCV: {e}")
            await session.rollback()

    def set_poll_interval(self, seconds: int) -> None:
        """Set the polling interval.

        Args:
            seconds: Polling interval in seconds
        """
        self._poll_interval = max(1, seconds)


# Global service instance
ohlcv_stream_service = OHLCVStreamService()