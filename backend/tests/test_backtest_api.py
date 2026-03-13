from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models.market import Market


def _build_ohlcv_rows() -> list[list[float]]:
    start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    closes = [100, 99, 98, 97, 99, 102, 105, 104, 101, 98, 95, 93]
    rows: list[list[float]] = []

    for index, close_price in enumerate(closes):
        open_price = closes[index - 1] if index > 0 else close_price
        high_price = max(open_price, close_price) + 1
        low_price = min(open_price, close_price) - 1
        timestamp = int((start + timedelta(hours=index)).timestamp() * 1000)
        rows.append([timestamp, open_price, high_price, low_price, close_price, 1000.0])

    return rows


@pytest.mark.asyncio
async def test_backtest_run_after_market_sync(async_client, db_session):
    class DummySyncExchangeService:
        def __init__(self, exchange_id: str):
            self.exchange_id = exchange_id

        async def initialize(self):
            return None

        async def close(self):
            return None

    async def fake_sync_markets(self, quote_allowlist=None, quote_denylist=None):
        self.session.add(
            Market(
                exchange=self.exchange_service.exchange_id,
                symbol="BTC/USDT",
                base_asset="BTC",
                quote_asset="USDT",
                active=True,
                meta={},
                exchange_symbol="BTC/USDT",
                price_precision=2,
                amount_precision=6,
            )
        )
        await self.session.commit()
        return 1

    class DummyBacktestExchangeService:
        def __init__(self, exchange_id: str):
            self.exchange_id = exchange_id
            self._rows = _build_ohlcv_rows()

        async def initialize(self):
            return None

        async def close(self):
            return None

        async def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None):
            filtered = [row for row in self._rows if since is None or row[0] >= since]
            return filtered[:limit] if limit is not None else filtered

    with patch("app.main.ExchangeService", DummySyncExchangeService):
        with patch("app.main.MarketService.sync_markets", new=fake_sync_markets):
            sync_response = await async_client.post(
                "/api/v1/markets/sync",
                json={"exchanges": ["binance"], "quote_allowlist": ["USDT"]},
            )

    assert sync_response.status_code == 200
    assert sync_response.json() == {"synced": 1}

    market = (
        await db_session.execute(select(Market).where(Market.symbol == "BTC/USDT"))
    ).scalar_one()

    with patch("app.api.v1.backtest.ExchangeService", DummyBacktestExchangeService):
        response = await async_client.post(
            "/api/v1/backtest/run",
            json={
                "market_id": market.id,
                "strategy": "ma_crossover",
                "start_date": "2026-03-01",
                "end_date": "2026-03-01",
                "initial_balance": 10000,
                "timeframe": "1h",
                "fast_period": 2,
                "slow_period": 3,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["initial_balance"] == 10000
    assert data["final_balance"] > 0
    assert data["total_trades"] == 1
    assert len(data["trades"]) == 1
    assert data["trades"][0]["symbol"] == "BTC/USDT"
    assert data["trades"][0]["side"] == "long"
    assert len(data["equity_curve"]) == len(_build_ohlcv_rows())


@pytest.mark.asyncio
async def test_backtest_run_uses_market_id_to_disambiguate_duplicate_symbols(async_client, db_session):
    market_a = Market(
        exchange="binance",
        symbol="BTC/USDT",
        base_asset="BTC",
        quote_asset="USDT",
        active=True,
        meta={},
        exchange_symbol="BTC/USDT",
        price_precision=2,
        amount_precision=6,
    )
    market_b = Market(
        exchange="bybit",
        symbol="BTC/USDT",
        base_asset="BTC",
        quote_asset="USDT",
        active=True,
        meta={},
        exchange_symbol="BTC/USDT",
        price_precision=2,
        amount_precision=6,
    )
    db_session.add_all([market_a, market_b])
    await db_session.commit()
    await db_session.refresh(market_a)
    await db_session.refresh(market_b)

    exchange_calls: list[str] = []

    class DummyBacktestExchangeService:
        def __init__(self, exchange_id: str):
            self.exchange_id = exchange_id
            self._rows = _build_ohlcv_rows()
            exchange_calls.append(exchange_id)

        async def initialize(self):
            return None

        async def close(self):
            return None

        async def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None):
            filtered = [row for row in self._rows if since is None or row[0] >= since]
            return filtered[:limit] if limit is not None else filtered

    with patch("app.api.v1.backtest.ExchangeService", DummyBacktestExchangeService):
        response = await async_client.post(
            "/api/v1/backtest/run",
            json={
                "market_id": market_b.id,
                "symbol": "BTC/USDT",
                "strategy": "ma_crossover",
                "start_date": "2026-03-01",
                "end_date": "2026-03-01",
                "initial_balance": 10000,
                "timeframe": "1h",
                "fast_period": 2,
                "slow_period": 3,
            },
        )

    assert response.status_code == 200
    assert exchange_calls == ["bybit"]


@pytest.mark.asyncio
async def test_backtest_run_rejects_unknown_strategy(async_client):
    response = await async_client.post(
        "/api/v1/backtest/run",
        json={
            "symbol": "BTC/USDT",
            "strategy": "definitely_not_real",
            "start_date": "2026-03-01",
            "end_date": "2026-03-01",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Unknown strategy: definitely_not_real"}


@pytest.mark.asyncio
async def test_backtest_run_requires_market_lookup(async_client):
    response = await async_client.post(
        "/api/v1/backtest/run",
        json={
            "strategy": "ma_crossover",
            "start_date": "2026-03-01",
            "end_date": "2026-03-01",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "market_id or symbol is required"}


@pytest.mark.asyncio
async def test_backtest_run_returns_not_found_for_unknown_market(async_client):
    response = await async_client.post(
        "/api/v1/backtest/run",
        json={
            "symbol": "MISSING/USDT",
            "strategy": "ma_crossover",
            "start_date": "2026-03-01",
            "end_date": "2026-03-01",
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Market not found: MISSING/USDT"}


@pytest.mark.asyncio
async def test_backtest_run_rejects_invalid_dates(async_client):
    response = await async_client.post(
        "/api/v1/backtest/run",
        json={
            "symbol": "BTC/USDT",
            "strategy": "ma_crossover",
            "start_date": "2026/03/01",
            "end_date": "2026-03-01",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid date format. Use ISO format."}
