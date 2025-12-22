"""Organizations API - GET and POST /api/v1/me/organizations"""

import os
import sys
import re
import json
import asyncio
import ssl
import enum
import logging
from uuid import UUID, uuid4
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from contextlib import asynccontextmanager

# SQLAlchemy
from sqlalchemy import String, ForeignKey, Enum, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Firebase
import firebase_admin
from firebase_admin import credentials, auth

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# DATABASE
# =============================================================================

DATABASE_URL = os.environ.get("DATABASE_URL", "")
_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None and DATABASE_URL:
        db_url = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        _engine = create_async_engine(
            db_url, pool_size=1, max_overflow=2, pool_pre_ping=True,
            connect_args={"ssl": ssl_ctx, "prepared_statement_cache_size": 0, "statement_cache_size": 0},
        )
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None and get_engine():
        _session_factory = async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)
    return _session_factory


@asynccontextmanager
async def get_db():
    factory = get_session_factory()
    if not factory:
        raise Exception("Database not configured")
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except:
            await session.rollback()
            raise


# =============================================================================
# MODELS
# =============================================================================

class Base(DeclarativeBase):
    pass


class SubscriptionTier(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    auth_provider: Mapped[str | None] = mapped_column(String(50))
    auth_provider_id: Mapped[str | None] = mapped_column(String(255))
    deleted_at: Mapped[datetime | None] = mapped_column()


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        Enum(SubscriptionTier, name="subscription_tier", values_callable=lambda x: [e.value for e in x]),
        default=SubscriptionTier.FREE
    )
    deleted_at: Mapped[datetime | None] = mapped_column()


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("organizations.id"))
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(50), default="member")


# =============================================================================
# FIREBASE AUTH
# =============================================================================

_firebase_app = None


def init_firebase():
    global _firebase_app
    if _firebase_app:
        return _firebase_app

    project_id = os.environ.get("FIREBASE_PROJECT_ID")
    client_email = os.environ.get("FIREBASE_CLIENT_EMAIL")
    private_key = os.environ.get("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n")

    if not all([project_id, client_email, private_key]):
        return None

    try:
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": project_id,
            "private_key": private_key,
            "client_email": client_email,
            "token_uri": "https://oauth2.googleapis.com/token",
        })
        _firebase_app = firebase_admin.initialize_app(cred)
        return _firebase_app
    except ValueError:
        return firebase_admin.get_app()
    except Exception as e:
        logger.error(f"Firebase init error: {e}")
        return None


def verify_token(token: str):
    if not init_firebase():
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
        logger.error(f"Token error: {e}")
        return None


# =============================================================================
# HANDLERS
# =============================================================================

async def get_or_create_user(session, fb_user):
    result = await session.execute(
        select(User).where(User.auth_provider == "firebase", User.auth_provider_id == fb_user["uid"], User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if user:
        return user

    user = User(
        id=uuid4(),
        email=fb_user.get("email") or f"{fb_user['uid']}@firebase.local",
        name=fb_user.get("name") or fb_user.get("email") or f"User {fb_user['uid'][-8:]}",
        avatar_url=fb_user.get("picture"),
        auth_provider="firebase",
        auth_provider_id=fb_user["uid"],
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_orgs(session, user_id):
    result = await session.execute(
        select(Organization, OrganizationMember.role)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user_id, Organization.deleted_at.is_(None))
        .order_by(Organization.name)
    )
    return {"organizations": [{"id": str(o.id), "name": o.name, "slug": o.slug, "role": r} for o, r in result.all()]}


async def create_org(session, user_id, name, slug):
    slug = re.sub(r'[^a-z0-9-]', '-', slug.lower().strip())
    slug = re.sub(r'-+', '-', slug).strip('-')

    if len(slug) < 3:
        return {"error": "Slug must be at least 3 characters"}, 400

    existing = await session.execute(select(Organization).where(Organization.slug == slug))
    if existing.scalar_one_or_none():
        return {"error": "Slug already exists"}, 400

    org = Organization(id=uuid4(), name=name, slug=slug, settings={}, subscription_tier=SubscriptionTier.FREE)
    session.add(org)

    member = OrganizationMember(id=uuid4(), organization_id=org.id, user_id=user_id, role="owner")
    session.add(member)

    await session.commit()
    return {"id": str(org.id), "name": org.name, "slug": org.slug, "role": "owner"}, 201


async def handle(method, headers, body):
    auth_header = headers.get("Authorization", headers.get("authorization", ""))
    if not auth_header.startswith("Bearer "):
        return {"error": "Not authenticated"}, 401

    fb_user = verify_token(auth_header[7:])
    if not fb_user:
        return {"error": "Invalid token"}, 401

    async with get_db() as session:
        user = await get_or_create_user(session, fb_user)

        if method == "GET":
            return await get_orgs(session, user.id), 200
        elif method == "POST":
            data = json.loads(body) if body else {}
            name, slug = data.get("name", "").strip(), data.get("slug", "").strip()
            if not name or not slug:
                return {"error": "Name and slug required"}, 400
            return await create_org(session, user.id, name, slug)

    return {"error": "Method not allowed"}, 405


# =============================================================================
# HANDLER CLASS
# =============================================================================

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")

    def _handle(self, method):
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode() if content_len > 0 else None

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result, status = loop.run_until_complete(handle(method, dict(self.headers), body))
            loop.close()

            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self._cors()
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self._cors()
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
