"""API routes for Imputable."""

from fastapi import APIRouter

from .audit import router as audit_router
from .audit_export import router as audit_export_router
from .auth import router as auth_router
from .decisions import router as decisions_router
from .ledger import router as ledger_router
from .risk_dashboard import router as risk_dashboard_router

# Main API router
api_router = APIRouter()

# Include all route modules
# Auth routes (login, dev-login)
api_router.include_router(auth_router)

# Ledger routes are the primary decision management endpoints
api_router.include_router(ledger_router)
api_router.include_router(audit_router)
api_router.include_router(audit_export_router)
api_router.include_router(risk_dashboard_router)

# Legacy routes (can be deprecated in favor of ledger routes)
api_router.include_router(decisions_router, prefix="/legacy", deprecated=True)

__all__ = ["api_router"]
