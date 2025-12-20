"""Security utilities: authentication, authorization, hashing."""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from .config import get_settings

settings = get_settings()

# Password hashing
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.bcrypt_rounds,
)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


# JWT Token handling
class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: str  # User ID
    org: str | None = None  # Current organization ID
    exp: datetime
    iat: datetime
    type: str = "access"  # "access" or "refresh"


def create_access_token(
    user_id: UUID,
    organization_id: UUID | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token."""
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )

    payload = {
        "sub": str(user_id),
        "org": str(organization_id) if organization_id else None,
        "exp": expire,
        "iat": now,
        "type": "access",
    }

    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_refresh_token(user_id: UUID) -> str:
    """Create a JWT refresh token."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.refresh_token_expire_days)

    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
        "type": "refresh",
    }

    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_token(token: str) -> TokenPayload | None:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return TokenPayload(**payload)
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# Content hashing for integrity
import hashlib


def hash_content(content: str) -> str:
    """Create SHA-256 hash of content for integrity verification."""
    return hashlib.sha256(content.encode()).hexdigest()


def verify_content_hash(content: str, expected_hash: str) -> bool:
    """Verify content matches its hash."""
    return hash_content(content) == expected_hash
