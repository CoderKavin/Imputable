"""Audit log API - GET /api/v1/audit"""

import os
import sys
import asyncio
from uuid import UUID

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from flask import Flask, request, jsonify
from sqlalchemy import select, desc, func

from api.lib.db import get_db_session, User, OrganizationMember, AuditLog
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


async def get_audit_logs(session, org_id: UUID, page: int, page_size: int, action: str | None, resource_type: str | None):
    """Get audit logs with pagination."""
    query = (
        select(AuditLog, User)
        .outerjoin(User, AuditLog.user_id == User.id)
        .where(AuditLog.organization_id == org_id)
    )

    if action:
        query = query.where(AuditLog.action == action)

    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    query = query.order_by(desc(AuditLog.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await session.execute(query)
    rows = result.all()

    items = []
    for log, user in rows:
        items.append({
            "id": str(log.id),
            "action": log.action.value if hasattr(log.action, 'value') else log.action,
            "resource_type": log.resource_type,
            "resource_id": str(log.resource_id),
            "details": log.details or {},
            "user": {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
            } if user else None,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
    }, 200


@app.route("/api/v1/audit", methods=["GET", "OPTIONS"])
def audit_handler():
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

            page = request.args.get("page", 1, type=int)
            page_size = request.args.get("page_size", 50, type=int)
            action = request.args.get("action")
            resource_type = request.args.get("resource_type")

            return await get_audit_logs(session, org_uuid, page, page_size, action, resource_type)

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
