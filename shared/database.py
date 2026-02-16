"""
Shared async database utilities for all microservices.
Uses asyncpg for non-blocking PostgreSQL access with connection pooling.
"""
import os
import asyncpg
from contextlib import asynccontextmanager


class Database:
    """Async database connection pool manager."""

    _pool: asyncpg.Pool | None = None

    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        """Return the existing pool or create one lazily."""
        if cls._pool is None:
            cls._pool = await asyncpg.create_pool(
                host=os.getenv("DB_HOST", "postgres"),
                port=int(os.getenv("DB_PORT", "5432")),
                database=os.getenv("DB_NAME", "voting_db"),
                user=os.getenv("DB_USER", "voting_user"),
                password=os.getenv("DB_PASSWORD", "voting_pass"),
                min_size=2,
                max_size=20,
            )
        return cls._pool

    @classmethod
    async def close(cls) -> None:
        """Gracefully close the pool (called on app shutdown)."""
        if cls._pool is not None:
            await cls._pool.close()
            cls._pool = None

    @classmethod
    @asynccontextmanager
    async def connection(cls):
        """Acquire a connection from the pool (auto-released on exit)."""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            yield conn

    @classmethod
    @asynccontextmanager
    async def transaction(cls):
        """Acquire a connection and open a transaction (auto-committed/rolled-back)."""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                yield conn
