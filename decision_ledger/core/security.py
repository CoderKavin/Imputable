"""Security utilities: authentication, authorization, hashing."""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID
import httpx
import logging

import jwt
from jwt import PyJWKClient
from passlib.context import CryptContext
from pydantic import BaseModel

from .config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Clerk JWKS client (cached)
_clerk_jwks_client: PyJWKClient | None = None


def get_clerk_jwks_client() -> PyJWKClient | None:
    """Get or create Clerk JWKS client for RS256 verification."""
    global _clerk_jwks_client

    if not settings.clerk_enabled:
        return None

    if _clerk_jwks_client is None:
        # Clerk JWKS URL format
        issuer = settings.clerk_issuer
        if issuer:
            jwks_url = f"{issuer}/.well-known/jwks.json"
            _clerk_jwks_client = PyJWKClient(jwks_url, cache_keys=True)
            logger.info(f"Initialized Clerk JWKS client with URL: {jwks_url}")

    return _clerk_jwks_client

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
    """Decode and validate a JWT token (legacy HS256)."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return TokenPayload(**payload)
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


class ClerkTokenPayload(BaseModel):
    """Clerk JWT token payload."""

    sub: str  # Clerk user ID (e.g., user_xxx)
    azp: str | None = None  # Authorized party (frontend URL)
    org_id: str | None = None  # Clerk organization ID
    org_role: str | None = None  # Role in organization
    org_slug: str | None = None  # Organization slug
    exp: datetime
    iat: datetime
    nbf: datetime | None = None
    iss: str | None = None  # Issuer

    # Additional Clerk claims
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    image_url: str | None = None

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p) or "Unknown User"


def decode_clerk_token(token: str) -> ClerkTokenPayload | None:
    """Decode and validate a Clerk JWT token using RS256."""
    jwks_client = get_clerk_jwks_client()

    if not jwks_client:
        logger.warning("Clerk JWKS client not configured")
        return None

    try:
        logger.info("Attempting to get signing key from JWKS")
        # Get the signing key from JWKS
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        logger.info("Got signing key, decoding token")

        # Decode and verify the token
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={
                "verify_aud": False,  # Clerk doesn't always include audience
            }
        )
        logger.info(f"Token decoded successfully, sub={payload.get('sub')}, org_id={payload.get('org_id')}")

        # Extract additional claims from session claims if present
        email = payload.get("email")
        first_name = payload.get("first_name")
        last_name = payload.get("last_name")
        image_url = payload.get("image_url")

        return ClerkTokenPayload(
            sub=payload["sub"],
            azp=payload.get("azp"),
            org_id=payload.get("org_id"),
            org_role=payload.get("org_role"),
            org_slug=payload.get("org_slug"),
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
            nbf=datetime.fromtimestamp(payload["nbf"], tz=timezone.utc) if payload.get("nbf") else None,
            iss=payload.get("iss"),
            email=email,
            first_name=first_name,
            last_name=last_name,
            image_url=image_url,
        )
    except jwt.ExpiredSignatureError:
        logger.warning("Clerk token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid Clerk token: {e}")
        return None
    except Exception as e:
        logger.error(f"Error decoding Clerk token: {e}")
        return None


# Content hashing for integrity
import hashlib


def hash_content(content: str) -> str:
    """Create SHA-256 hash of content for integrity verification."""
    return hashlib.sha256(content.encode()).hexdigest()


def verify_content_hash(content: str, expected_hash: str) -> bool:
    """Verify content matches its hash."""
    return hash_content(content) == expected_hash
