"""Organizations API endpoint - GET and POST /api/v1/me/organizations"""

import os
import json
import asyncio
import re
import ssl
import logging
from uuid import uuid4

from flask import Flask, request, jsonify

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

import firebase_admin
from firebase_admin import credentials, auth

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ============================================================================
# Database Setup
# ============================================================================

DATABASE_URL = os.environ.get("DATABASE_URL", "")
db_url_async = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://") if DATABASE_URL else ""

engine = None
async_session_factory = None

if db_url_async:
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    engine = create_async_engine(
        db_url_async,
        pool_size=1,
        max_overflow=2,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={
            "ssl": ssl_context,
            "prepared_statement_cache_size": 0,
            "statement_cache_size": 0,
        },
    )
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

# ============================================================================
# Models (inline to avoid import issues)
# ============================================================================

import enum
from datetime import datetime
from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SubscriptionTier(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid4] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    auth_provider: Mapped[str | None] = mapped_column(String(50))
    auth_provider_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[uuid4] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(Enum(SubscriptionTier), default=SubscriptionTier.FREE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    id: Mapped[uuid4] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[uuid4] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    user_id: Mapped[uuid4] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ============================================================================
# Firebase Auth
# ============================================================================

_firebase_app = None


def get_firebase_app():
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
        logger.info("Firebase initialized")
        return _firebase_app
    except Exception as e:
        logger.error(f"Firebase init error: {e}")
        return None


def verify_token(token: str) -> dict | None:
    app = get_firebase_app()
    if not app:
        return None
    try:
        decoded = auth.verify_id_token(token)
        return {
            "uid": decoded.get("uid", decoded.get("user_id", "")),
            "email": decoded.get("email"),
            "name": decoded.get("name"),
            "picture": decoded.get("picture"),
        }
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return None


# ============================================================================
# Async Helpers
# ============================================================================

async def get_or_create_user(session: AsyncSession, firebase_user: dict) -> User:
    result = await session.execute(
        select(User).where(
            User.auth_provider == "firebase",
            User.auth_provider_id == firebase_user["uid"],
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if user:
        return user

    user = User(
        id=uuid4(),
        email=firebase_user.get("email") or f"{firebase_user['uid']}@firebase.local",
        name=firebase_user.get("name") or firebase_user.get("email") or f"User {firebase_user['uid'][-8:]}",
        avatar_url=firebase_user.get("picture"),
        auth_provider="firebase",
        auth_provider_id=firebase_user["uid"],
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_organizations(session: AsyncSession, user_id):
    result = await session.execute(
        select(Organization, OrganizationMember.role)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(
            OrganizationMember.user_id == user_id,
            Organization.deleted_at.is_(None),
        )
        .order_by(Organization.name)
    )
    return result.all()


async def create_organization(session: AsyncSession, user_id, name: str, slug: str):
    # Clean slug
    slug = slug.lower().strip()
    slug = re.sub(r'[^a-z0-9-]', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')

    if len(slug) < 3:
        return None, "Slug must be at least 3 characters"

    # Check existing
    existing = await session.execute(
        select(Organization).where(Organization.slug == slug)
    )
    if existing.scalar_one_or_none():
        return None, "An organization with this slug already exists"

    org = Organization(
        id=uuid4(),
        name=name,
        slug=slug,
        settings={},
        subscription_tier=SubscriptionTier.FREE,
    )
    session.add(org)

    membership = OrganizationMember(
        id=uuid4(),
        organization_id=org.id,
        user_id=user_id,
        role="owner",
    )
    session.add(membership)

    await session.commit()
    await session.refresh(org)
    return org, None


# ============================================================================
# Flask Routes
# ============================================================================

def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Organization-ID"
    return response


@app.after_request
def after_request(response):
    return add_cors_headers(response)


@app.route("/api/v1/me/organizations", methods=["GET", "POST", "OPTIONS"])
def organizations_handler():
    if request.method == "OPTIONS":
        return "", 204

    # Check database
    if not async_session_factory:
        return jsonify({"error": "Database not configured"}), 500

    # Get auth token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Not authenticated"}), 401

    token = auth_header.replace("Bearer ", "")
    firebase_user = verify_token(token)

    if not firebase_user:
        return jsonify({"error": "Invalid or expired token"}), 401

    # Run async operations
    async def handle_request():
        async with async_session_factory() as session:
            try:
                user = await get_or_create_user(session, firebase_user)

                if request.method == "GET":
                    rows = await get_user_organizations(session, user.id)
                    organizations = [
                        {
                            "id": str(org.id),
                            "name": org.name,
                            "slug": org.slug,
                            "role": role,
                        }
                        for org, role in rows
                    ]
                    return {"organizations": organizations}, 200

                elif request.method == "POST":
                    data = request.get_json() or {}
                    name = data.get("name", "").strip()
                    slug = data.get("slug", "").strip()

                    if not name:
                        return {"error": "Name is required"}, 400
                    if not slug:
                        return {"error": "Slug is required"}, 400

                    org, error = await create_organization(session, user.id, name, slug)
                    if error:
                        return {"error": error}, 400

                    return {
                        "id": str(org.id),
                        "name": org.name,
                        "slug": org.slug,
                        "role": "owner",
                    }, 201

            except Exception as e:
                logger.error(f"Request error: {e}", exc_info=True)
                await session.rollback()
                return {"error": str(e)}, 500

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result, status = loop.run_until_complete(handle_request())
        loop.close()
        return jsonify(result), status
    except Exception as e:
        logger.error(f"Handler error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# For Vercel
handler = app
