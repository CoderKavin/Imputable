"""Organizations API - GET and POST /api/v1/me/organizations"""

import os
import sys
import re
import json
import asyncio
from uuid import uuid4
from http.server import BaseHTTPRequestHandler

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import select
from api.lib.db import get_db_session, Organization, OrganizationMember, SubscriptionTier
from api.lib.auth import verify_token, get_or_create_user


def cors_response(handler, status=200, body=None):
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Organization-ID")
    handler.end_headers()
    if body:
        handler.wfile.write(json.dumps(body).encode())


async def get_user_organizations(session, user_id):
    result = await session.execute(
        select(Organization, OrganizationMember.role)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(
            OrganizationMember.user_id == user_id,
            Organization.deleted_at.is_(None),
        )
        .order_by(Organization.name)
    )
    rows = result.all()
    return {
        "organizations": [
            {"id": str(org.id), "name": org.name, "slug": org.slug, "role": role}
            for org, role in rows
        ]
    }


async def create_organization(session, user_id, name: str, slug: str):
    slug = slug.lower().strip()
    slug = re.sub(r'[^a-z0-9-]', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')

    if len(slug) < 3:
        return {"error": "Slug must be at least 3 characters"}, 400

    existing = await session.execute(select(Organization).where(Organization.slug == slug))
    if existing.scalar_one_or_none():
        return {"error": "An organization with this slug already exists"}, 400

    org = Organization(id=uuid4(), name=name, slug=slug, settings={}, subscription_tier=SubscriptionTier.FREE)
    session.add(org)

    membership = OrganizationMember(id=uuid4(), organization_id=org.id, user_id=user_id, role="owner")
    session.add(membership)

    await session.commit()
    await session.refresh(org)

    return {"id": str(org.id), "name": org.name, "slug": org.slug, "role": "owner"}, 201


async def handle_request(method, headers, body):
    auth_header = headers.get("Authorization", headers.get("authorization", ""))
    if not auth_header.startswith("Bearer "):
        return {"error": "Not authenticated"}, 401

    token = auth_header[7:]
    firebase_user = verify_token(token)
    if not firebase_user:
        return {"error": "Invalid token"}, 401

    async with get_db_session() as session:
        user = await get_or_create_user(session, firebase_user)

        if method == "GET":
            result = await get_user_organizations(session, user.id)
            return result, 200

        elif method == "POST":
            data = json.loads(body) if body else {}
            name = data.get("name", "").strip()
            slug = data.get("slug", "").strip()

            if not name:
                return {"error": "Name is required"}, 400
            if not slug:
                return {"error": "Slug is required"}, 400

            return await create_organization(session, user.id, name, slug)

    return {"error": "Method not allowed"}, 405


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        cors_response(self, 204)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def _handle(self, method):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode() if content_length > 0 else None

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result, status = loop.run_until_complete(handle_request(method, dict(self.headers), body))
            loop.close()

            cors_response(self, status, result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            cors_response(self, 500, {"error": str(e)})
