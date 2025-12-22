"""Decision detail API - GET, PUT /api/v1/decisions/[id]"""

import os
import sys
import json
import asyncio
import hashlib
from uuid import UUID, uuid4
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from flask import Flask, request, jsonify
from sqlalchemy import select, func

from api.lib.db import (
    get_db_session, User, OrganizationMember,
    Decision, DecisionVersion, ImpactLevel
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


async def get_decision(session, decision_id: UUID, version: int | None = None):
    """Get a decision, optionally at a specific version."""
    # Get decision
    result = await session.execute(
        select(Decision, User)
        .join(User, Decision.created_by == User.id)
        .where(Decision.id == decision_id, Decision.deleted_at.is_(None))
    )
    row = result.first()
    if not row:
        return {"error": "Decision not found"}, 404

    decision, creator = row

    # Get version
    if version:
        version_result = await session.execute(
            select(DecisionVersion, User)
            .join(User, DecisionVersion.created_by == User.id)
            .where(
                DecisionVersion.decision_id == decision_id,
                DecisionVersion.version_number == version,
            )
        )
    else:
        version_result = await session.execute(
            select(DecisionVersion, User)
            .join(User, DecisionVersion.created_by == User.id)
            .where(DecisionVersion.id == decision.current_version_id)
        )

    version_row = version_result.first()
    if not version_row:
        return {"error": "Version not found"}, 404

    dec_version, version_creator = version_row

    # Get version count
    count_result = await session.execute(
        select(func.count()).where(DecisionVersion.decision_id == decision_id)
    )
    version_count = count_result.scalar() or 1

    is_current = decision.current_version_id == dec_version.id

    return {
        "id": str(decision.id),
        "organization_id": str(decision.organization_id),
        "decision_number": decision.decision_number,
        "status": decision.status.value if hasattr(decision.status, 'value') else decision.status,
        "created_by": {
            "id": str(creator.id),
            "name": creator.name,
            "email": creator.email,
        },
        "created_at": decision.created_at.isoformat() if decision.created_at else None,
        "version": {
            "id": str(dec_version.id),
            "version_number": dec_version.version_number,
            "title": dec_version.title,
            "impact_level": dec_version.impact_level.value if hasattr(dec_version.impact_level, 'value') else dec_version.impact_level,
            "content": dec_version.content or {},
            "tags": dec_version.tags or [],
            "content_hash": dec_version.content_hash,
            "created_by": {
                "id": str(version_creator.id),
                "name": version_creator.name,
            },
            "created_at": dec_version.created_at.isoformat() if dec_version.created_at else None,
            "change_summary": dec_version.change_summary,
            "is_current": is_current,
        },
        "version_count": version_count,
        "requested_version": version,
    }, 200


async def amend_decision(session, decision_id: UUID, user_id: UUID, data: dict):
    """Amend a decision (create new version)."""
    # Get decision
    result = await session.execute(
        select(Decision).where(Decision.id == decision_id, Decision.deleted_at.is_(None))
    )
    decision = result.scalar_one_or_none()
    if not decision:
        return {"error": "Decision not found"}, 404

    title = data.get("title", "").strip()
    content = data.get("content", {})
    impact_level = data.get("impact_level", "medium")
    tags = data.get("tags", [])
    change_summary = data.get("change_summary", "").strip()

    if not title:
        return {"error": "Title is required"}, 400
    if not change_summary:
        return {"error": "Change summary is required"}, 400

    # Get current version number
    version_result = await session.execute(
        select(func.max(DecisionVersion.version_number))
        .where(DecisionVersion.decision_id == decision_id)
    )
    current_version = version_result.scalar() or 0
    new_version_number = current_version + 1

    # Create content hash
    content_str = json.dumps(content, sort_keys=True)
    content_hash = hashlib.sha256(content_str.encode()).hexdigest()

    # Create new version
    version_id = uuid4()
    version = DecisionVersion(
        id=version_id,
        decision_id=decision_id,
        version_number=new_version_number,
        title=title,
        impact_level=ImpactLevel(impact_level) if impact_level in [e.value for e in ImpactLevel] else ImpactLevel.MEDIUM,
        content=content,
        tags=tags,
        created_by=user_id,
        change_summary=change_summary,
        content_hash=content_hash,
    )
    session.add(version)

    # Update decision
    decision.current_version_id = version_id

    await session.commit()

    # Return updated decision
    return await get_decision(session, decision_id)


@app.route("/api/v1/decisions/<decision_id>", methods=["GET", "PUT", "OPTIONS"])
def decision_handler(decision_id):
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

    try:
        decision_uuid = UUID(decision_id)
    except ValueError:
        return jsonify({"error": "Invalid decision ID"}), 400

    async def handle():
        async with get_db_session() as session:
            user = await get_or_create_user(session, firebase_user)

            try:
                org_uuid = UUID(org_id)
            except ValueError:
                return {"error": "Invalid organization ID"}, 400

            # Verify org membership
            membership = await session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.organization_id == org_uuid,
                    OrganizationMember.user_id == user.id,
                )
            )
            if not membership.scalar_one_or_none():
                return {"error": "Not a member of this organization"}, 403

            if request.method == "GET":
                version = request.args.get("version", type=int)
                return await get_decision(session, decision_uuid, version)

            elif request.method == "PUT":
                data = request.get_json() or {}
                return await amend_decision(session, decision_uuid, user.id, data)

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
