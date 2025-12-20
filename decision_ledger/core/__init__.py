"""Core application utilities."""

from .config import Settings, get_settings
from .database import (
    TenantContext,
    async_session_factory,
    close_db,
    engine,
    get_session,
    get_session_context,
    init_db,
    set_tenant_context,
)
from .dependencies import (
    AdminDep,
    CurrentUser,
    CurrentUserDep,
    OrgContextDep,
    OwnerDep,
    SessionDep,
    get_current_user,
    require_admin,
    require_org_context,
    require_owner,
)
from .security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_content,
    hash_password,
    verify_content_hash,
    verify_password,
)

__all__ = [
    # Config
    "Settings",
    "get_settings",
    # Database
    "engine",
    "async_session_factory",
    "get_session",
    "get_session_context",
    "init_db",
    "close_db",
    "set_tenant_context",
    "TenantContext",
    # Dependencies
    "CurrentUser",
    "get_current_user",
    "require_org_context",
    "require_admin",
    "require_owner",
    "CurrentUserDep",
    "OrgContextDep",
    "AdminDep",
    "OwnerDep",
    "SessionDep",
    # Security
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "hash_content",
    "verify_content_hash",
]
