"""Decisions API - GET (list) and POST (create) /api/v1/decisions"""

import os
import sys
import json
import asyncio
import hashlib
from uuid import uuid4
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from flask import Flask, request, jsonify
from sqlalchemy import select, func, desc

from api.lib.db import (
    get_db_session, User, Organization, OrganizationMember,
    Decision, DecisionVersion, DecisionStatus, ImpactLevel
)
from api.lib.auth import verify_token, get_or_create_user, get_auth_from_request

app = Flask(__name__)


def cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Organization-ID",
    }


@app.after_request
def after_request(response):
    for key, value in cors_headers().items():
        response.headers[key] = value
    return response


async def get_next_decision_number(session, org_id) -> int:
    """Get the next decision number for an organization."""
    result = await session.execute(
        select(func.coalesce(func.max(Decision.decision_number), 0))
        .where(Decision.organization_id == org_id)
    )
    return result.scalar() + 1


async def list_decisions(session, org_id, page: int, page_size: int, status_filter: str | None, search: str | None):
    """List decisions with pagination."""
    # Base query
    query = (
        select(Decision, DecisionVersion, User)
        .join(DecisionVersion, Decision.current_version_id == DecisionVersion.id)
        .join(User, Decision.created_by == User.id)
        .where(
            Decision.organization_id == org_id,
            Decision.deleted_at.is_(None),
        )
    )

    # Apply status filter
    if status_filter:
        try:
            status = DecisionStatus(status_filter)
            query = query.where(Decision.status == status)
        except ValueError:
            pass

    # Apply search filter
    if search:
        search_pattern = f"%{search}%"
        query = query.where(DecisionVersion.title.ilike(search_pattern))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    query = query.order_by(desc(Decision.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await session.execute(query)
    rows = result.all()

    items = []
    for decision, version, creator in rows:
        # Get version count
        version_count_result = await session.execute(
            select(func.count()).where(DecisionVersion.decision_id == decision.id)
        )
        version_count = version_count_result.scalar() or 1

        items.append({
            "id": str(decision.id),
            "organization_id": str(decision.organization_id),
            "decision_number": decision.decision_number,
            "status": decision.status.value if hasattr(decision.status, 'value') else decision.status,
            "title": version.title,
            "impact_level": version.impact_level.value if hasattr(version.impact_level, 'value') else version.impact_level,
            "tags": version.tags or [],
            "created_by": {
                "id": str(creator.id),
                "name": creator.name,
                "email": creator.email,
            },
            "created_at": decision.created_at.isoformat() if decision.created_at else None,
            "version_count": version_count,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
    }


async def create_decision(session, org_id, user_id, data: dict):
    """Create a new decision."""
    title = data.get("title", "").strip()
    content = data.get("content", {})
    impact_level = data.get("impact_level", "medium")
    tags = data.get("tags", [])

    if not title:
        return {"error": "Title is required"}, 400

    # Get next decision number
    decision_number = await get_next_decision_number(session, org_id)

    # Create decision
    decision_id = uuid4()
    version_id = uuid4()

    decision = Decision(
        id=decision_id,
        organization_id=org_id,
        decision_number=decision_number,
        status=DecisionStatus.DRAFT,
        created_by=user_id,
    )
    session.add(decision)

    # Create content hash
    content_str = json.dumps(content, sort_keys=True)
    content_hash = hashlib.sha256(content_str.encode()).hexdigest()

    # Create first version
    version = DecisionVersion(
        id=version_id,
        decision_id=decision_id,
        version_number=1,
        title=title,
        impact_level=ImpactLevel(impact_level) if impact_level in [e.value for e in ImpactLevel] else ImpactLevel.MEDIUM,
        content=content,
        tags=tags,
        created_by=user_id,
        change_summary="Initial version",
        content_hash=content_hash,
    )
    session.add(version)

    # Update decision with current version
    await session.flush()
    decision.current_version_id = version_id

    await session.commit()

    # Fetch creator for response
    creator_result = await session.execute(select(User).where(User.id == user_id))
    creator = creator_result.scalar_one()

    return {
        "id": str(decision.id),
        "organization_id": str(decision.organization_id),
        "decision_number": decision.decision_number,
        "status": decision.status.value,
        "created_by": {
            "id": str(creator.id),
            "name": creator.name,
            "email": creator.email,
        },
        "created_at": decision.created_at.isoformat() if decision.created_at else datetime.utcnow().isoformat(),
        "version": {
            "id": str(version.id),
            "version_number": version.version_number,
            "title": version.title,
            "impact_level": version.impact_level.value,
            "content": version.content,
            "tags": version.tags or [],
            "content_hash": version.content_hash,
            "created_by": {
                "id": str(creator.id),
                "name": creator.name,
            },
            "created_at": version.created_at.isoformat() if version.created_at else datetime.utcnow().isoformat(),
            "change_summary": version.change_summary,
            "is_current": True,
        },
        "version_count": 1,
    }, 201


@app.route("/api/v1/decisions", methods=["GET", "POST", "OPTIONS"])
def decisions_handler():
    if request.method == "OPTIONS":
        return "", 204

    # Auth check
    token = get_auth_from_request(dict(request.headers))
    if not token:
        return jsonify({"error": "Not authenticated"}), 401

    firebase_user = verify_token(token)
    if not firebase_user:
        return jsonify({"error": "Invalid token"}), 401

    org_id = request.headers.get("X-Organization-ID")
    if not org_id:
        return jsonify({"error": "X-Organization-ID header required"}), 400

    async def handle():
        async with get_db_session() as session:
            user = await get_or_create_user(session, firebase_user)

            # Verify org membership
            from uuid import UUID
            try:
                org_uuid = UUID(org_id)
            except ValueError:
                return {"error": "Invalid organization ID"}, 400

            membership = await session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.organization_id == org_uuid,
                    OrganizationMember.user_id == user.id,
                )
            )
            if not membership.scalar_one_or_none():
                return {"error": "Not a member of this organization"}, 403

            if request.method == "GET":
                page = request.args.get("page", 1, type=int)
                page_size = request.args.get("page_size", 20, type=int)
                status = request.args.get("status")
                search = request.args.get("search")

                result = await list_decisions(session, org_uuid, page, page_size, status, search)
                return result, 200

            elif request.method == "POST":
                data = request.get_json() or {}
                return await create_decision(session, org_uuid, user.id, data)

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
