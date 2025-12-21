"""Imputable: Main FastAPI Application.

A system of record for engineering and product decisions with
immutable versioning, audit trails, and approval workflows.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import api_router
from .core import close_db, get_settings, init_db
from .schemas import ErrorResponse

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    import os

    # Debug: print config
    db_url = str(settings.database_url) if hasattr(settings, 'database_url') else "NOT SET"
    print(f"[STARTUP] ENVIRONMENT: {os.getenv('ENVIRONMENT')}")
    print(f"[STARTUP] DATABASE_URL from env: {os.getenv('DATABASE_URL', 'NOT SET')[:50]}...")
    print(f"[STARTUP] DATABASE_URL from settings: {db_url[:50]}...")

    # Startup - skip init_db in production (tables already exist)
    if os.getenv("ENVIRONMENT") != "production":
        try:
            await init_db()
        except Exception as e:
            print(f"Warning: Could not initialize database: {e}")
    yield
    # Shutdown
    await close_db()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    ## Imputable API

    A **system of record** for engineering and product decisions.

    ### Key Features

    - **Immutable Versioning**: Decisions are never modified in place. Every edit creates a new version.
    - **Audit Trail**: Complete history of who viewed, modified, and approved each decision.
    - **Approval Workflows**: Required sign-offs with configurable reviewers.
    - **Decision Graph**: Track relationships like "supersedes", "blocked by", and "related to".
    - **Multi-Tenancy**: Strict organization isolation with row-level security.

    ### Authentication

    All endpoints require a valid JWT token in the `Authorization: Bearer <token>` header.

    For organization-scoped operations, include the `X-Organization-ID` header.
    """,
    openapi_url=f"{settings.api_prefix}/openapi.json",
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=f"{settings.api_prefix}/redoc",
    lifespan=lifespan,
)

# CORS middleware
print(f"[CORS] Allowed origins: {settings.allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    import traceback
    error_detail = str(exc)
    # In development/debug mode, include full traceback
    if settings.debug or settings.environment != "production":
        error_detail = f"{str(exc)}\n{traceback.format_exc()}"

    print(f"[ERROR] Unhandled exception: {error_detail}")

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="internal_error",
            message=f"An unexpected error occurred: {str(exc)[:200]}",
            details=[],
        ).model_dump(),
    )


# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version}


@app.get("/debug/config", tags=["debug"])
async def debug_config():
    """Debug endpoint to check configuration (development only)."""
    import os
    db_url = str(settings.database_url) if hasattr(settings, 'database_url') else "NOT SET"
    # Mask the password in the URL
    if "@" in db_url:
        parts = db_url.split("@")
        before_at = parts[0]
        after_at = parts[1] if len(parts) > 1 else ""
        if ":" in before_at:
            # Mask password
            creds = before_at.rsplit(":", 1)
            masked = f"{creds[0]}:****@{after_at}"
        else:
            masked = db_url[:30] + "..."
    else:
        masked = db_url[:30] + "..."

    return {
        "environment": os.getenv("ENVIRONMENT", "not set"),
        "database_url_from_env": os.getenv("DATABASE_URL", "NOT SET")[:50] + "..." if os.getenv("DATABASE_URL") else "NOT SET",
        "database_url_from_settings": masked,
        "secret_key_set": settings.secret_key != "change-me-in-production-use-strong-random-key",
    }


# Include API routes
app.include_router(api_router, prefix=settings.api_prefix)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "decision_ledger.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
