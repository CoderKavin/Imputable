"""Database connection and session management.

Transaction Guarantees:
- Each request gets its own session
- All operations within a request are atomic
- On any exception, the entire transaction is rolled back
- Sessions are properly closed after each request
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID
import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Create async engine with connection pooling
# Add SSL requirement for cloud databases (Supabase, Neon, etc.)
import ssl
import os
import socket
from urllib.parse import urlparse, urlunparse

connect_args = {}
db_url = str(settings.database_url)

# Force IPv4 for Railway/serverless platforms that have IPv6 issues
def resolve_hostname_to_ipv4(url: str) -> str:
    """Resolve hostname to IPv4 address to avoid IPv6 connectivity issues."""
    try:
        parsed = urlparse(url.replace("postgresql://", "http://").replace("postgresql+asyncpg://", "http://"))
        hostname = parsed.hostname
        if hostname:
            # Try to resolve to IPv4
            try:
                ipv4_info = socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM)
                if ipv4_info:
                    ipv4_addr = ipv4_info[0][4][0]
                    logger.info(f"Resolved {hostname} to IPv4: {ipv4_addr}")
                    # Replace hostname with IP in URL
                    return url.replace(hostname, ipv4_addr)
            except socket.gaierror as e:
                logger.warning(f"Could not resolve {hostname} to IPv4: {e}")
    except Exception as e:
        logger.warning(f"Error resolving hostname: {e}")
    return url

# Always use SSL for production/cloud databases
if os.getenv("ENVIRONMENT") == "production" or "supabase" in db_url or "neon" in db_url or "pooler" in db_url:
    # Create SSL context for cloud databases
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    connect_args["ssl"] = ssl_context
    # Disable prepared statements for pgbouncer compatibility (Supabase uses pgbouncer)
    connect_args["prepared_statement_cache_size"] = 0
    connect_args["statement_cache_size"] = 0
    logger.info(f"Using SSL for database connection with pgbouncer compatibility")

    # Force IPv4 resolution to avoid "Network unreachable" errors on Railway
    if os.getenv("FORCE_IPV4", "true").lower() == "true":
        db_url = resolve_hostname_to_ipv4(db_url)
        logger.info(f"Forced IPv4 resolution for database connection")

logger.info(f"Database URL (masked): {db_url[:30]}...")

# Build async URL from the (possibly IPv4-resolved) db_url
db_url_async = db_url.replace("postgresql://", "postgresql+asyncpg://")
logger.info(f"Async Database URL (masked): {db_url_async[:40]}...")

engine = create_async_engine(
    db_url_async,
    pool_size=10,  # Keep more connections ready
    max_overflow=20,  # Allow more overflow connections
    echo=settings.database_echo,
    pool_pre_ping=True,  # Check connection health before use
    pool_recycle=300,  # Recycle connections every 5 minutes (faster turnover)
    pool_timeout=30,  # Wait up to 30s for a connection
    connect_args=connect_args,
)

# Session factory - creates new sessions for each request
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Don't expire objects after commit
    autoflush=False,         # Manual flush for better control
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a transactional database session.

    Transaction Behavior:
    - Session starts in a transaction automatically
    - On successful completion: COMMIT
    - On any exception: ROLLBACK (automatic)
    - Session is always closed properly

    Usage in FastAPI:
        @router.post("/items")
        async def create_item(session: SessionDep):
            # All operations here are in one transaction
            session.add(item1)
            session.add(item2)  # If this fails, item1 is also rolled back
            # Commit happens automatically after the endpoint returns
    """
    async with async_session_factory() as session:
        try:
            # Begin implicit transaction
            yield session
            # If we get here without exception, commit
            await session.commit()
            logger.debug("Transaction committed successfully")
        except SQLAlchemyError as e:
            # Database error - rollback
            await session.rollback()
            logger.error(f"Database error, transaction rolled back: {e}")
            raise
        except Exception as e:
            # Any other error - also rollback for safety
            await session.rollback()
            logger.error(f"Error during request, transaction rolled back: {e}")
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_session_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions (for use outside FastAPI)."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


class TenantContext:
    """Context manager for setting RLS context variables.

    Usage:
        async with TenantContext(session, org_id, user_id):
            # All queries in this block will be scoped to the org
            results = await session.execute(...)
    """

    def __init__(
        self,
        session: AsyncSession,
        organization_id: UUID,
        user_id: UUID | None = None,
    ):
        self.session = session
        self.organization_id = organization_id
        self.user_id = user_id

    async def __aenter__(self) -> "TenantContext":
        # Set session variables for RLS
        # Note: SET LOCAL doesn't support parameters, so we format directly
        await self.session.execute(
            text(f"SET LOCAL app.current_organization_id = '{str(self.organization_id)}'")
        )
        if self.user_id:
            await self.session.execute(
                text(f"SET LOCAL app.current_user_id = '{str(self.user_id)}'")
            )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        # Variables are automatically reset at end of transaction
        pass


async def set_tenant_context(
    session: AsyncSession,
    organization_id: UUID,
    user_id: UUID | None = None,
) -> None:
    """Set RLS context variables for the current session.

    Call this at the start of each request to enable row-level security.
    Note: SET commands don't support parameterized queries, so we use string formatting.
    The UUID values are validated before this point, so this is safe.
    """
    # SET LOCAL doesn't support parameters, so we format the string directly
    # UUIDs are validated by the caller, so this is safe from SQL injection
    await session.execute(
        text(f"SET LOCAL app.current_organization_id = '{str(organization_id)}'")
    )
    if user_id:
        await session.execute(
            text(f"SET LOCAL app.current_user_id = '{str(user_id)}'")
        )


async def init_db() -> None:
    """Initialize database (create tables if needed)."""
    from ..models import Base

    async with engine.begin() as conn:
        # In production, use Alembic migrations instead
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
