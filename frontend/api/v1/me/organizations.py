"""Organizations API - GET and POST /api/v1/me/organizations"""

import os
import sys
import re
import asyncio
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from flask import Flask, request, jsonify
from sqlalchemy import select

from api.lib.db import get_db_session, User, Organization, OrganizationMember, SubscriptionTier
from api.lib.auth import verify_token, get_or_create_user, get_auth_from_request

app = Flask(__name__)


def cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Organization-ID",
    }


@app.after_request
def after_request(response):
    for key, value in cors_headers().items():
        response.headers[key] = value
    return response


async def get_user_organizations(session, user_id):
    """Get all organizations for a user."""
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
            {
                "id": str(org.id),
                "name": org.name,
                "slug": org.slug,
                "role": role,
            }
            for org, role in rows
        ]
    }, 200


async def create_organization(session, user_id, name: str, slug: str):
    """Create a new organization."""
    # Clean slug
    slug = slug.lower().strip()
    slug = re.sub(r'[^a-z0-9-]', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')

    if len(slug) < 3:
        return {"error": "Slug must be at least 3 characters"}, 400

    # Check existing
    existing = await session.execute(
        select(Organization).where(Organization.slug == slug)
    )
    if existing.scalar_one_or_none():
        return {"error": "An organization with this slug already exists"}, 400

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

    return {
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "role": "owner",
    }, 201


@app.route("/api/v1/me/organizations", methods=["GET", "POST", "OPTIONS"])
def organizations_handler():
    if request.method == "OPTIONS":
        return "", 204

    token = get_auth_from_request(dict(request.headers))
    if not token:
        return jsonify({"error": "Not authenticated"}), 401

    firebase_user = verify_token(token)
    if not firebase_user:
        return jsonify({"error": "Invalid token"}), 401

    async def handle():
        async with get_db_session() as session:
            user = await get_or_create_user(session, firebase_user)

            if request.method == "GET":
                return await get_user_organizations(session, user.id)

            elif request.method == "POST":
                data = request.get_json() or {}
                name = data.get("name", "").strip()
                slug = data.get("slug", "").strip()

                if not name:
                    return {"error": "Name is required"}, 400
                if not slug:
                    return {"error": "Slug is required"}, 400

                return await create_organization(session, user.id, name, slug)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result, status = loop.run_until_complete(handle())
        loop.close()
        return jsonify(result), status
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


handler = app
