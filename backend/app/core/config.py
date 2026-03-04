from typing import Optional

from pydantic import PostgresDsn, RedisDsn, computed_field
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_ignore_empty=True, extra="ignore"
    )

    # PostgreSQL Configuration
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    DB_POOL_PRE_PING: bool = True
    DB_POOL_RECYCLE_SECONDS: int = 1800

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_USER: Optional[str] = None
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_SOCKET_CONNECT_TIMEOUT: int = 5
    REDIS_SOCKET_TIMEOUT: int = 5

    # Scheduler Configuration
    SCHEDULER_ENABLED: bool = True
    AUTO_SYNC_INTERVAL_MINUTES: int = 1
    MARKET_SYNC_HOUR: int = 0  # Hour of day (0-23) to sync market data
    BACKFILL_CHECK_INTERVAL_HOURS: int = 1

    # Concurrency Control
    MAX_CONCURRENT_SYNCS: int = 3  # Max concurrent exchange API calls

    # Exchange Configuration
    EXCHANGES: list[str] = ["binance"]  # List of exchanges to sync

    # Authentication Configuration
    SECRET_KEY: str = "change-me-in-production"  # Must be set in production
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    API_KEY_HEADER: str = "X-API-Key"
    RATE_LIMIT_PER_MINUTE: int = 100
    RATE_LIMIT_ENABLED: bool = True

    @computed_field
    @property
    def DATABASE_URL(self) -> PostgresDsn:
        return MultiHostUrl.build(
            scheme="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    @computed_field
    @property
    def REDIS_URL(self) -> RedisDsn:
        if self.REDIS_PASSWORD:
            return MultiHostUrl.build(
                scheme="redis",
                username=self.REDIS_USER,
                password=self.REDIS_PASSWORD,
                host=self.REDIS_HOST,
                port=self.REDIS_PORT,
                path=str(self.REDIS_DB),
            )
        return MultiHostUrl.build(
            scheme="redis",
            host=self.REDIS_HOST,
            port=self.REDIS_PORT,
            path=str(self.REDIS_DB),
        )


settings = Settings()
