"""Firebase authentication for Vercel Python functions."""

import os
import logging
from dataclasses import dataclass
from uuid import uuid4

import firebase_admin
from firebase_admin import credentials, auth
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_firebase_app = None


def get_firebase_app():
    """Initialize Firebase Admin SDK."""
    global _firebase_app

    if _firebase_app is not None:
        return _firebase_app

    project_id = os.environ.get("FIREBASE_PROJECT_ID")
    client_email = os.environ.get("FIREBASE_CLIENT_EMAIL")
    private_key = os.environ.get("FIREBASE_PRIVATE_KEY")

    if not all([project_id, client_email, private_key]):
        logger.warning("Firebase credentials not configured")
        return None

    if private_key:
        private_key = private_key.replace("\\n", "\n")

    try:
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": project_id,
            "private_key": private_key,
            "client_email": client_email,
            "token_uri": "https://oauth2.googleapis.com/token",
        })
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized successfully")
        return _firebase_app
    except ValueError:
        # Already initialized
        _firebase_app = firebase_admin.get_app()
        return _firebase_app
    except Exception as e:
        logger.error(f"Firebase init error: {e}")
        return None


@dataclass
class FirebaseUser:
    uid: str
    email: str | None
    name: str | None
    picture: str | None


def verify_token(token: str) -> FirebaseUser | None:
    """Verify Firebase ID token."""
    app = get_firebase_app()
    if not app:
        return None

    try:
        decoded = auth.verify_id_token(token)
        return FirebaseUser(
            uid=decoded.get("uid", decoded.get("user_id", "")),
            email=decoded.get("email"),
            name=decoded.get("name"),
            picture=decoded.get("picture"),
        )
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return None


async def get_or_create_user(session: AsyncSession, firebase_user: FirebaseUser) -> User:
    """Get or create user from Firebase data."""
    result = await session.execute(
        select(User).where(
            User.auth_provider == "firebase",
            User.auth_provider_id == firebase_user.uid,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if user:
        return user

    user = User(
        id=uuid4(),
        email=firebase_user.email or f"{firebase_user.uid}@firebase.local",
        name=firebase_user.name or firebase_user.email or f"User {firebase_user.uid[-8:]}",
        avatar_url=firebase_user.picture,
        auth_provider="firebase",
        auth_provider_id=firebase_user.uid,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def get_auth_from_request(headers: dict) -> str | None:
    """Extract Bearer token from request headers."""
    auth_header = headers.get("authorization", headers.get("Authorization", ""))
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None
