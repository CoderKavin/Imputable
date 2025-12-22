"""Security utilities: authentication, authorization, hashing."""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID
import logging

import jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from .config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Firebase Admin SDK (lazy initialization)
_firebase_app = None


def get_firebase_app():
    """Get or initialize Firebase Admin SDK."""
    global _firebase_app

    if not settings.firebase_enabled:
        return None

    if _firebase_app is None:
        try:
            import firebase_admin
            from firebase_admin import credentials

            # Handle the private key - it may have escaped newlines
            private_key = settings.firebase_private_key
            if private_key:
                # Replace escaped newlines with actual newlines
                private_key = private_key.replace("\\n", "\n")

            cred = credentials.Certificate({
                "type": "service_account",
                "project_id": settings.firebase_project_id,
                "client_email": settings.firebase_client_email,
                "private_key": private_key,
                "token_uri": "https://oauth2.googleapis.com/token",
            })
            _firebase_app = firebase_admin.initialize_app(cred)
            logger.info(f"Firebase Admin SDK initialized for project: {settings.firebase_project_id}")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
            return None

    return _firebase_app


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


class FirebaseTokenPayload(BaseModel):
    """Firebase JWT token payload."""

    uid: str  # Firebase user ID
    email: str | None = None
    email_verified: bool = False
    name: str | None = None
    picture: str | None = None
    sign_in_provider: str | None = None  # password, google.com, etc.
    exp: datetime
    iat: datetime
    iss: str | None = None  # Issuer


def decode_firebase_token(token: str) -> FirebaseTokenPayload | None:
    """Decode and validate a Firebase ID token."""
    app = get_firebase_app()

    if not app:
        logger.warning("Firebase app not configured")
        return None

    try:
        from firebase_admin import auth

        logger.info("Verifying Firebase ID token")
        # Verify the ID token
        decoded_token = auth.verify_id_token(token)
        logger.info(f"Token verified for uid={decoded_token.get('uid')}, email={decoded_token.get('email')}")

        # Extract sign-in provider from firebase claims
        firebase_claims = decoded_token.get("firebase", {})
        sign_in_provider = firebase_claims.get("sign_in_provider")

        return FirebaseTokenPayload(
            uid=decoded_token["uid"],
            email=decoded_token.get("email"),
            email_verified=decoded_token.get("email_verified", False),
            name=decoded_token.get("name"),
            picture=decoded_token.get("picture"),
            sign_in_provider=sign_in_provider,
            exp=datetime.fromtimestamp(decoded_token["exp"], tz=timezone.utc),
            iat=datetime.fromtimestamp(decoded_token["iat"], tz=timezone.utc),
            iss=decoded_token.get("iss"),
        )
    except Exception as e:
        logger.warning(f"Firebase token verification failed: {e}")
        return None


# Content hashing for integrity
import hashlib


def hash_content(content: str) -> str:
    """Create SHA-256 hash of content for integrity verification."""
    return hashlib.sha256(content.encode()).hexdigest()


def verify_content_hash(content: str, expected_hash: str) -> bool:
    """Verify content matches its hash."""
    return hash_content(content) == expected_hash
