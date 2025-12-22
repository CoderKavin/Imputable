"""Database connection for Vercel Python functions."""

import os
import ssl
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Get database URL from environment
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Convert to async URL
db_url_async = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# SSL configuration for Supabase
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

connect_args = {
    "ssl": ssl_context,
    "prepared_statement_cache_size": 0,
    "statement_cache_size": 0,
}

engine = create_async_engine(
    db_url_async,
    pool_size=1,
    max_overflow=2,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args=connect_args,
) if DATABASE_URL else None

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
) if engine else None


async def get_session():
    """Get a database session."""
    if not async_session_factory:
        raise Exception("Database not configured")
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
