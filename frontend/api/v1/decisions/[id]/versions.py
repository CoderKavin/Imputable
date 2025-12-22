"""Decision versions API - GET /api/v1/decisions/[id]/versions"""

import os
import sys
import asyncio
from uuid import UUID

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from flask import Flask, request, jsonify
from sqlalchemy import select, desc

from api.lib.db import get_db_session, User, OrganizationMember, Decision, DecisionVersion
from api.lib.auth import verify_token, get_or_create_user, get_auth_from_request

app = Flask(__name__)


def cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Organization-ID",
    }


@app.after_request
def after_request(response):
    for key, value in cors_headers().items():
        response.headers[key] = value
    return response


async def get_versions(session, decision_id: UUID):
    """Get all versions of a decision."""
    # Verify decision exists
    decision_result = await session.execute(
        select(Decision).where(Decision.id == decision_id, Decision.deleted_at.is_(None))
    )
    if not decision_result.scalar_one_or_none():
        return {"error": "Decision not found"}, 404

    # Get versions
    result = await session.execute(
        select(DecisionVersion, User)
        .join(User, DecisionVersion.created_by == User.id)
        .where(DecisionVersion.decision_id == decision_id)
        .order_by(desc(DecisionVersion.version_number))
    )
    rows = result.all()

    versions = []
    for version, creator in rows:
        versions.append({
            "id": str(version.id),
            "version_number": version.version_number,
            "title": version.title,
            "impact_level": version.impact_level.value if hasattr(version.impact_level, 'value') else version.impact_level,
            "content_hash": version.content_hash,
            "created_by": {
                "id": str(creator.id),
                "name": creator.name,
            },
            "created_at": version.created_at.isoformat() if version.created_at else None,
            "change_summary": version.change_summary,
        })

    return versions, 200


@app.route("/api/v1/decisions/<decision_id>/versions", methods=["GET", "OPTIONS"])
def versions_handler(decision_id):
    if request.method == "OPTIONS":
        return "", 204

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

            membership = await session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.organization_id == org_uuid,
                    OrganizationMember.user_id == user.id,
                )
            )
            if not membership.scalar_one_or_none():
                return {"error": "Not a member of this organization"}, 403

            return await get_versions(session, decision_uuid)

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
