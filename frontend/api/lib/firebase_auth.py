"""Firebase authentication for Vercel Python functions."""

import os
import json
import logging
from dataclasses import dataclass

import firebase_admin
from firebase_admin import credentials, auth

logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
_firebase_app = None


def get_firebase_app():
    """Get or initialize Firebase app."""
    global _firebase_app

    if _firebase_app is not None:
        return _firebase_app

    project_id = os.environ.get("FIREBASE_PROJECT_ID")
    client_email = os.environ.get("FIREBASE_CLIENT_EMAIL")
    private_key = os.environ.get("FIREBASE_PRIVATE_KEY")

    if not all([project_id, client_email, private_key]):
        logger.warning("Firebase credentials not fully configured")
        return None

    # Handle escaped newlines in private key
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
        logger.info("Firebase Admin SDK initialized successfully")
        return _firebase_app
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")
        return None


@dataclass
class FirebaseUser:
    """Firebase user data."""
    uid: str
    email: str | None
    name: str | None
    picture: str | None


def verify_firebase_token(token: str) -> FirebaseUser | None:
    """Verify a Firebase ID token and return user data."""
    app = get_firebase_app()
    if not app:
        logger.error("Firebase not initialized")
        return None

    try:
        decoded = auth.verify_id_token(token)
        return FirebaseUser(
            uid=decoded.get("uid", decoded.get("user_id", "")),
            email=decoded.get("email"),
            name=decoded.get("name"),
            picture=decoded.get("picture"),
        )
    except auth.InvalidIdTokenError as e:
        logger.warning(f"Invalid Firebase token: {e}")
        return None
    except auth.ExpiredIdTokenError:
        logger.warning("Expired Firebase token")
        return None
    except Exception as e:
        logger.error(f"Firebase token verification error: {e}")
        return None
