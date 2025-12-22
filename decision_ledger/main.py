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

# CORS middleware with explicit origins (credentials require explicit origins, not "*")
cors_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:8000",
    "https://imputable.vercel.app",
    "https://www.imputable.vercel.app",
]

# Add any additional configured origins
configured_origins = settings.allowed_origins
for origin in configured_origins:
    if origin and origin not in cors_origins:
        cors_origins.append(origin)

print(f"[CORS] Allowed origins: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,
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


from pydantic import BaseModel as PydanticBaseModel
from typing import Optional

class TokenTestRequest(PydanticBaseModel):
    authorization: Optional[str] = None

@app.post("/debug/test-token", tags=["debug"])
async def test_token(request: TokenTestRequest):
    """Test endpoint to debug token verification."""
    from .core.security import decode_firebase_token, decode_token

    authorization = request.authorization or ""
    # Extract token from "Bearer xxx" format
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization

    if not token:
        return {"error": "No token provided", "hint": "Send JSON body with {\"authorization\": \"Bearer <token>\"}"}

    result = {
        "token_preview": token[:50] + "..." if len(token) > 50 else token,
        "firebase_enabled": settings.firebase_enabled,
    }

    # Try Firebase decode
    if settings.firebase_enabled:
        firebase_payload = decode_firebase_token(token)
        if firebase_payload:
            result["firebase_decode"] = {
                "success": True,
                "uid": firebase_payload.uid,
                "email": firebase_payload.email,
                "name": firebase_payload.name,
                "sign_in_provider": firebase_payload.sign_in_provider,
            }
        else:
            result["firebase_decode"] = {"success": False, "error": "Failed to decode as Firebase token"}

    # Try legacy decode
    legacy_payload = decode_token(token)
    if legacy_payload:
        result["legacy_decode"] = {
            "success": True,
            "sub": legacy_payload.sub,
            "org": legacy_payload.org,
        }
    else:
        result["legacy_decode"] = {"success": False}

    return result


from fastapi import Header

@app.post("/debug/test-auth", tags=["debug"])
async def test_auth(
    request: TokenTestRequest,
    x_organization_id: str | None = Header(default=None, alias="X-Organization-ID"),
):
    """Test full auth flow including DB operations."""
    from .core.security import decode_firebase_token
    from .core.database import get_session
    from .core.dependencies import get_or_create_firebase_user, get_user_organization

    authorization = request.authorization or ""
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization

    if not token:
        return {"error": "No token provided"}

    # Decode Firebase token
    firebase_payload = decode_firebase_token(token)
    if not firebase_payload:
        return {"error": "Failed to decode Firebase token"}

    result = {
        "firebase_uid": firebase_payload.uid,
        "email": firebase_payload.email,
        "header_org_id": x_organization_id,
    }

    # Try DB operations
    try:
        async for session in get_session():
            # Create user
            user = await get_or_create_firebase_user(session, firebase_payload)
            result["db_user_id"] = str(user.id)
            result["db_user_email"] = user.email

            # Get organization if header provided
            if x_organization_id:
                org, role = await get_user_organization(session, user, x_organization_id)
                if org:
                    result["db_org_id"] = str(org.id)
                    result["db_org_slug"] = org.slug
                    result["db_org_role"] = role

            result["success"] = True
            break
    except Exception as e:
        import traceback
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()
        result["success"] = False

    return result


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
        "firebase_enabled": settings.firebase_enabled,
        "firebase_project_id": settings.firebase_project_id,
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
