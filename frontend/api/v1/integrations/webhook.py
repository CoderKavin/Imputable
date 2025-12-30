"""Unified Slack & Teams webhook handler.

Single endpoint that routes:
- POST /api/v1/integrations/webhook?platform=slack&type=command
- POST /api/v1/integrations/webhook?platform=slack&type=interactions
- POST /api/v1/integrations/webhook?platform=teams
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import hashlib
import hmac
import time
import re
from urllib.parse import urlparse, parse_qs, unquote
from uuid import uuid4
from datetime import datetime
import urllib.request


# =============================================================================
# AI ANALYSIS
# =============================================================================

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"

AI_SYSTEM_PROMPT = """You are an AI assistant specialized in extracting engineering decisions from team chat conversations.

Your task is to analyze the provided conversation transcript and extract a structured decision record.

IMPORTANT GUIDELINES:
1. Be concise but complete - summarize don't copy verbatim
2. If something isn't clear from the conversation, indicate uncertainty
3. Look for explicit decisions, not just discussions
4. Identify who disagreed and why (key dissenters)
5. Note any deadlines or timelines mentioned
6. Assess whether there was clear consensus
7. DETECT GATEKEEPERS: If someone mentions that a specific person needs to approve/sign off before proceeding, capture that person as "required_approver" and set status to "pending_review"
8. DETECT CONFLICTS: If there's active disagreement with no resolution (e.g., "I disagree", "I'm against this", "strictly against"), set "has_conflict" to true and status to "draft"
9. DETECT MISSING INFO: If the conversation lacks context, alternatives, or clear decision details, set "missing_info_warning" with a helpful message

OUTPUT FORMAT (JSON):
{
    "title": "Short descriptive title for the decision (max 100 chars)",
    "context": "Summary of the problem being solved and why a decision was needed. If unclear, use empty string.",
    "choice": "What was actually decided - the chosen approach. If no clear decision, use empty string.",
    "rationale": "Why this choice was made - the reasoning",
    "alternatives": [
        {"name": "Alternative option name", "rejected_reason": "Why it wasn't chosen"}
    ],
    "key_dissenters": ["Names of people who disagreed or raised concerns"],
    "deadlines": ["Any deadlines or timelines mentioned"],
    "required_approver": "@PersonName or null - person explicitly mentioned as needing to approve/sign off",
    "suggested_status": "approved|pending_review|draft",
    "suggested_impact": "low|medium|high|critical",
    "confidence_score": 0.0-1.0,
    "has_conflict": false,
    "missing_info_warning": "Warning message if information is insufficient, or null if adequate",
    "analysis_notes": "Brief notes on analysis certainty"
}

STATUS GUIDELINES:
- "approved": Clear consensus, everyone agreed, decision is final, NO ONE mentioned needing additional approval
- "pending_review": Decision made but:
  * Someone specific was mentioned as needing to approve (gatekeeper pattern), OR
  * There are unresolved concerns that need addressing
- "draft": Use when:
  * The discussion is still ongoing with no resolution
  * There's active conflict/disagreement without consensus
  * The conversation is too vague to determine a decision
  * Very little information is available

GATEKEEPER DETECTION (CRITICAL):
Look for patterns like:
- "@PersonName needs to approve this"
- "but [Name] needs to sign off"
- "waiting for [Name]'s approval"
- "[Name] has final say on this"
- "check with [Name] before we proceed"
If detected, set required_approver to that person's name (include @ if mentioned) and status to "pending_review"

CONFLICT DETECTION (CRITICAL):
Look for unresolved disagreements:
- "I disagree" / "I'm against this" / "strictly against"
- Back-and-forth debate with no final agreement
- Someone says "no" or blocks without resolution
If detected, set has_conflict to true, status to "draft"

MISSING INFO DETECTION (CRITICAL):
Set missing_info_warning if:
- No clear problem/context is stated → "Context not specified in thread"
- No alternatives were discussed → "No alternatives mentioned"
- The entire message is just "Let's go with X" with no explanation → "Minimal context provided - please fill in details manually"
- Very short conversation with little substance → "Limited discussion found - please verify details"

CONFIDENCE GUIDELINES:
- 0.9-1.0: Very clear decision with explicit consensus
- 0.7-0.9: Clear decision but some interpretation needed
- 0.5-0.7: Decision exists but context is incomplete
- 0.3-0.5: Possible decision, significant uncertainty
- 0.0-0.3: Very unclear, may not be a decision at all (has_conflict or missing_info likely true)"""


def analyze_with_gemini(messages: list, channel_name: str = None, hint: str = None) -> dict:
    """Analyze messages with Google Gemini API.

    Args:
        messages: List of message dicts with author, text, timestamp
        channel_name: Optional channel name for context
        hint: Optional hint from user about what decision to focus on
    """
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        return None

    # Format transcript
    lines = []
    if channel_name:
        lines.append(f"Channel: #{channel_name}\n")
    if hint:
        lines.append(f"User hint: Focus on the discussion about '{hint}'\n")
    lines.append("=== CONVERSATION TRANSCRIPT ===\n")
    for msg in messages:
        author = msg.get("author", "Unknown")
        text = msg.get("text", "")
        lines.append(f"{author}:\n  {text}\n")
    lines.append("=== END TRANSCRIPT ===")
    transcript = "\n".join(lines)

    # Build the analysis prompt
    analysis_prompt = "\n\nAnalyze this conversation and extract the decision"
    if hint:
        analysis_prompt += f" (focusing on: {hint})"
    analysis_prompt += f":\n\n{transcript}"

    # Call Gemini
    url = f"{GEMINI_API_URL}?key={gemini_key}"
    payload = json.dumps({
        "contents": [{
            "parts": [
                {"text": AI_SYSTEM_PROMPT},
                {"text": analysis_prompt}
            ]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.8,
            "maxOutputTokens": 2048,
            "responseMimeType": "application/json"
        }
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    try:
        response = urllib.request.urlopen(req, timeout=30)
        data = json.loads(response.read().decode())

        # Extract text from response
        candidates = data.get("candidates", [])
        if not candidates:
            return None

        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")

        # Parse JSON from response
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        result = json.loads(text.strip())

        # Ensure we got a dict, not a list or other type
        if not isinstance(result, dict):
            print(f"Gemini returned non-dict type: {type(result)}")
            return None

        return result
    except Exception as e:
        print(f"Gemini API error: {e}")
        return None


def semantic_search_decisions(query: str, decisions: list) -> dict:
    """Use Gemini to find the most relevant decisions based on semantic understanding.

    Args:
        query: The user's search query (natural language)
        decisions: List of decision dicts with id, decision_number, title, content, status, created_at

    Returns:
        dict with 'matches' (list of decision IDs ranked by relevance) and 'explanation'
    """
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key or not decisions:
        return {"matches": [], "explanation": "No results found."}

    # Format decisions for the prompt
    decision_summaries = []
    for d in decisions:
        content = d.get("content", {})
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except:
                content = {"context": content}

        summary = f"""
DECISION-{d['decision_number']} (ID: {d['id']})
Title: {d['title']}
Status: {d['status']}
Created: {d.get('created_at', 'Unknown')}
Context: {content.get('context', 'N/A')[:300]}
Decision: {content.get('choice', 'N/A')[:300]}
"""
        decision_summaries.append(summary)

    decisions_text = "\n---\n".join(decision_summaries)

    search_prompt = f"""You are a search assistant for a decision log system.
A user is searching for past decisions. Understand their intent (not just keywords) and find the most relevant decisions.

USER SEARCH QUERY: "{query}"

AVAILABLE DECISIONS:
{decisions_text}

Analyze the user's query and find decisions that match their intent. Consider:
- Semantic similarity (e.g., "database migration" matches "Postgres Migration")
- Topic relevance (e.g., "auth" matches decisions about "authentication", "login", "OAuth")
- Temporal context clues (e.g., "that thing we decided last month" if dates match)

Return a JSON object with:
- "matches": array of decision IDs (just the UUID strings) ranked by relevance, max 5
- "explanation": a brief, friendly explanation of what you found (1-2 sentences)
- "best_match_summary": if there's a strong match, a one-line summary of why it's relevant

Example response:
{{"matches": ["uuid1", "uuid2"], "explanation": "Found 2 decisions about database migrations. The June decision specifically covers Postgres.", "best_match_summary": "DECISION-42 from June 12th decided to use Postgres for the migration."}}

If no relevant decisions found, return:
{{"matches": [], "explanation": "No decisions found matching your search. Try different keywords or check /decision list for recent decisions."}}
"""

    url = f"{GEMINI_API_URL}?key={gemini_key}"
    payload = json.dumps({
        "contents": [{
            "parts": [{"text": search_prompt}]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "topP": 0.8,
            "maxOutputTokens": 1024,
            "responseMimeType": "application/json"
        }
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    try:
        response = urllib.request.urlopen(req, timeout=15)
        data = json.loads(response.read().decode())

        candidates = data.get("candidates", [])
        if not candidates:
            return {"matches": [], "explanation": "Search service unavailable."}

        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")

        # Parse JSON from response
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        result = json.loads(text.strip())
        return result
    except Exception as e:
        print(f"Semantic search error: {e}")
        return {"matches": [], "explanation": "Search failed. Try a simpler query."}


def fetch_slack_thread(token: str, channel_id: str, thread_ts: str) -> list:
    """Fetch all messages in a Slack thread."""
    messages = []

    url = f"https://slack.com/api/conversations.replies?channel={channel_id}&ts={thread_ts}&limit=100"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})

    try:
        response = urllib.request.urlopen(req, timeout=10)
        data = json.loads(response.read().decode())

        if data.get("ok"):
            for msg in data.get("messages", []):
                if msg.get("subtype") in ("bot_message", "channel_join", "channel_leave"):
                    continue
                messages.append({
                    "author": msg.get("user", "Unknown"),
                    "text": msg.get("text", ""),
                    "timestamp": msg.get("ts", "")
                })
    except Exception as e:
        print(f"Slack API error: {e}")

    return messages


def fetch_channel_context(token: str, channel_id: str, target_ts: str, count: int = 25) -> list:
    """Fetch messages around a target message in a channel for context.

    Gets messages before and after the target message to provide context
    for AI analysis when the message isn't part of a thread.
    """
    messages = []

    # Fetch messages before and including the target (oldest first)
    # Using latest=target_ts to get messages up to and including target
    url_before = f"https://slack.com/api/conversations.history?channel={channel_id}&latest={target_ts}&limit={count}&inclusive=true"
    req = urllib.request.Request(url_before, headers={"Authorization": f"Bearer {token}"})

    try:
        response = urllib.request.urlopen(req, timeout=10)
        data = json.loads(response.read().decode())

        if data.get("ok"):
            for msg in data.get("messages", []):
                if msg.get("subtype") in ("bot_message", "channel_join", "channel_leave"):
                    continue
                # Skip thread replies (they have thread_ts different from ts)
                if msg.get("thread_ts") and msg.get("thread_ts") != msg.get("ts"):
                    continue
                messages.append({
                    "author": msg.get("user", "Unknown"),
                    "text": msg.get("text", ""),
                    "timestamp": msg.get("ts", ""),
                    "is_target": msg.get("ts") == target_ts
                })
    except Exception as e:
        print(f"Slack API error fetching messages before: {e}")

    # Fetch messages after the target
    url_after = f"https://slack.com/api/conversations.history?channel={channel_id}&oldest={target_ts}&limit={count}&inclusive=false"
    req = urllib.request.Request(url_after, headers={"Authorization": f"Bearer {token}"})

    try:
        response = urllib.request.urlopen(req, timeout=10)
        data = json.loads(response.read().decode())

        if data.get("ok"):
            for msg in data.get("messages", []):
                if msg.get("subtype") in ("bot_message", "channel_join", "channel_leave"):
                    continue
                # Skip thread replies
                if msg.get("thread_ts") and msg.get("thread_ts") != msg.get("ts"):
                    continue
                # Skip the target message (already included)
                if msg.get("ts") == target_ts:
                    continue
                messages.append({
                    "author": msg.get("user", "Unknown"),
                    "text": msg.get("text", ""),
                    "timestamp": msg.get("ts", ""),
                    "is_target": False
                })
    except Exception as e:
        print(f"Slack API error fetching messages after: {e}")

    # Sort by timestamp (oldest first)
    messages.sort(key=lambda m: float(m["timestamp"]))

    return messages


def fetch_recent_channel_messages(token: str, channel_id: str, limit: int = 50) -> list:
    """Fetch the most recent messages from a channel for AI analysis.

    Used by the /log slash command to analyze recent conversation.
    """
    messages = []

    url = f"https://slack.com/api/conversations.history?channel={channel_id}&limit={limit}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})

    try:
        response = urllib.request.urlopen(req, timeout=10)
        data = json.loads(response.read().decode())

        if data.get("ok"):
            for msg in data.get("messages", []):
                # Skip bot messages and system messages
                if msg.get("subtype") in ("bot_message", "channel_join", "channel_leave", "channel_topic", "channel_purpose"):
                    continue
                # Skip thread replies (they have thread_ts different from ts)
                if msg.get("thread_ts") and msg.get("thread_ts") != msg.get("ts"):
                    continue
                messages.append({
                    "author": msg.get("user", "Unknown"),
                    "text": msg.get("text", ""),
                    "timestamp": msg.get("ts", "")
                })

            # Reverse to get chronological order (oldest first)
            messages.reverse()
    except Exception as e:
        print(f"Slack API error fetching recent messages: {e}")

    return messages


def resolve_slack_user_names(token: str, messages: list) -> list:
    """Resolve Slack user IDs to display names."""
    user_ids = set()
    for msg in messages:
        author = msg.get("author", "")
        if author.startswith("U"):
            user_ids.add(author)

    user_names = {}
    for user_id in user_ids:
        url = f"https://slack.com/api/users.info?user={user_id}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            response = urllib.request.urlopen(req, timeout=5)
            data = json.loads(response.read().decode())
            if data.get("ok"):
                user = data.get("user", {})
                user_names[user_id] = user.get("real_name") or user.get("name") or user_id
        except Exception:
            user_names[user_id] = user_id

    for msg in messages:
        author = msg.get("author", "")
        if author in user_names:
            msg["author"] = user_names[author]

    return messages


# =============================================================================
# HELPERS
# =============================================================================

def get_slack_user_info(token: str, user_id: str) -> dict:
    """Get Slack user info including email.

    Returns dict with keys: id, email, name, real_name
    Returns None if user not found or API error.
    """
    url = f"https://slack.com/api/users.info?user={user_id}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        response = urllib.request.urlopen(req, timeout=5)
        data = json.loads(response.read().decode())
        if data.get("ok"):
            user = data.get("user", {})
            return {
                "id": user.get("id"),
                "email": user.get("profile", {}).get("email"),
                "name": user.get("name"),
                "real_name": user.get("real_name") or user.get("profile", {}).get("real_name"),
            }
    except Exception as e:
        print(f"[SLACK] Error getting user info for {user_id}: {e}")
    return None


def lookup_slack_user_by_name(token: str, name: str) -> dict:
    """Look up a Slack user by @mention name or display name.

    Args:
        token: Slack bot token
        name: User name like "@sarah", "sarah", or "Sarah (CFO)"

    Returns dict with keys: id, email, name, real_name or None if not found.
    """
    # Clean the name - remove @ prefix and parenthetical notes
    clean_name = name.strip()
    if clean_name.startswith("@"):
        clean_name = clean_name[1:]
    # Remove parenthetical like "(CFO)"
    if "(" in clean_name:
        clean_name = clean_name.split("(")[0].strip()

    # Use users.list to find the user (for small workspaces)
    # For larger workspaces, you'd want users.lookupByEmail if you have email
    url = "https://slack.com/api/users.list?limit=500"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        response = urllib.request.urlopen(req, timeout=10)
        data = json.loads(response.read().decode())
        if data.get("ok"):
            clean_lower = clean_name.lower()
            for user in data.get("members", []):
                if user.get("deleted") or user.get("is_bot"):
                    continue
                # Match by username, display name, or real name
                if (user.get("name", "").lower() == clean_lower or
                    user.get("real_name", "").lower() == clean_lower or
                    user.get("profile", {}).get("display_name", "").lower() == clean_lower or
                    user.get("profile", {}).get("real_name", "").lower() == clean_lower):
                    return {
                        "id": user.get("id"),
                        "email": user.get("profile", {}).get("email"),
                        "name": user.get("name"),
                        "real_name": user.get("real_name") or user.get("profile", {}).get("real_name"),
                    }
    except Exception as e:
        print(f"[SLACK] Error looking up user by name '{name}': {e}")
    return None


def resolve_or_create_user_from_slack(conn, org_id: str, slack_user_info: dict, added_by_user_id: str) -> str:
    """Find or create an Imputable user from Slack user info.

    First tries to match by email, then by slack_user_id.
    Creates a new user if no match found.

    Returns the user_id (UUID string).
    """
    from sqlalchemy import text

    slack_id = slack_user_info.get("id")
    email = slack_user_info.get("email")
    real_name = slack_user_info.get("real_name") or slack_user_info.get("name") or "Slack User"

    # Try to find by email first (most reliable for matching existing users)
    if email:
        result = conn.execute(text("""
            SELECT id FROM users WHERE email = :email AND deleted_at IS NULL
        """), {"email": email})
        row = result.fetchone()
        if row:
            user_id = str(row[0])
            # Update their slack_user_id if not set
            conn.execute(text("""
                UPDATE users SET slack_user_id = :slack_id, updated_at = NOW()
                WHERE id = :user_id AND (slack_user_id IS NULL OR slack_user_id = '')
            """), {"slack_id": slack_id, "user_id": user_id})
            return user_id

    # Try to find by slack_user_id
    if slack_id:
        result = conn.execute(text("""
            SELECT id FROM users WHERE slack_user_id = :slack_id AND deleted_at IS NULL
        """), {"slack_id": slack_id})
        row = result.fetchone()
        if row:
            return str(row[0])

    # Create new user
    user_id = str(uuid4())
    user_email = email or f"{slack_id}@slack.local"
    conn.execute(text("""
        INSERT INTO users (id, email, name, slack_user_id, auth_provider, created_at, updated_at)
        VALUES (:id, :email, :name, :slack_id, 'slack', NOW(), NOW())
    """), {"id": user_id, "email": user_email, "name": real_name, "slack_id": slack_id})

    # Add them to the organization
    conn.execute(text("""
        INSERT INTO organization_members (id, organization_id, user_id, role, created_at)
        VALUES (:id, :org_id, :user_id, 'member', NOW())
        ON CONFLICT (organization_id, user_id) DO NOTHING
    """), {"id": str(uuid4()), "org_id": org_id, "user_id": user_id})

    return user_id


def get_active_member_user_id(conn, org_id: str, slack_user_id: str) -> tuple:
    """Check if a Slack user is an active member and return their user_id.

    Returns:
        (user_id, status, error_message) where:
        - user_id: UUID string if user is active, None otherwise
        - status: "active", "inactive", or "not_found"
        - error_message: Error message to show user, or None if active
    """
    from sqlalchemy import text

    result = conn.execute(text("""
        SELECT u.id, om.status
        FROM users u
        JOIN organization_members om ON om.user_id = u.id AND om.organization_id = :org_id
        WHERE u.slack_user_id = :slack_id AND u.deleted_at IS NULL
    """), {"org_id": org_id, "slack_id": slack_user_id})
    row = result.fetchone()

    if row:
        user_id, status = str(row[0]), row[1] or "active"
        if status == "inactive":
            return (None, "inactive", "Your account is inactive. Ask your organization admin to activate your account.")
        return (user_id, "active", None)

    return (None, "not_found", "You're not a member of this Imputable workspace. Ask your organization admin to add you.")


def send_approval_dm(token: str, approver_slack_id: str, decision_id: str, decision_number: int,
                     title: str, requester_name: str, context: str = None) -> dict:
    """Send a DM to the approver with approve/reject buttons.

    Returns dict with {success: bool, channel_id: str, message_ts: str} or {success: False} on error.
    """
    decision_url = f"https://imputable.vercel.app/decisions/{decision_id}"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🔔 Approval Requested", "emoji": True}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<{decision_url}|DECISION-{decision_number}: {title}>*"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{requester_name}* has requested your approval on this decision."
            }
        },
    ]

    if context:
        # Truncate context for display
        display_context = context[:300] + "..." if len(context) > 300 else context
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"_{display_context}_"}
        })

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "actions",
        "block_id": f"approval_{decision_id}",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "✅ Approve", "emoji": True},
                "style": "primary",
                "action_id": "approve_decision",
                "value": decision_id,
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "❌ Reject", "emoji": True},
                "style": "danger",
                "action_id": "reject_decision",
                "value": decision_id,
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Details", "emoji": True},
                "url": decision_url,
                "action_id": "view_decision",
            },
        ]
    })
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": "You were identified as a required approver for this decision."}]
    })

    # Open a DM channel with the user
    dm_url = "https://slack.com/api/conversations.open"
    dm_payload = json.dumps({"users": approver_slack_id}).encode()
    dm_req = urllib.request.Request(dm_url, data=dm_payload, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    })

    try:
        dm_response = urllib.request.urlopen(dm_req, timeout=5)
        dm_data = json.loads(dm_response.read().decode())
        if not dm_data.get("ok"):
            print(f"[SLACK] Error opening DM with {approver_slack_id}: {dm_data.get('error')}")
            return {"success": False}

        channel_id = dm_data.get("channel", {}).get("id")

        # Send the message
        msg_url = "https://slack.com/api/chat.postMessage"
        msg_payload = json.dumps({
            "channel": channel_id,
            "text": f"Approval requested for DECISION-{decision_number}: {title}",
            "blocks": blocks
        }).encode()
        msg_req = urllib.request.Request(msg_url, data=msg_payload, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        })

        msg_response = urllib.request.urlopen(msg_req, timeout=5)
        msg_data = json.loads(msg_response.read().decode())
        if not msg_data.get("ok"):
            print(f"[SLACK] Error sending approval DM: {msg_data.get('error')}")
            return {"success": False}

        message_ts = msg_data.get("ts")
        print(f"[SLACK] Sent approval DM to {approver_slack_id} for DECISION-{decision_number} (ts={message_ts})")
        return {"success": True, "channel_id": channel_id, "message_ts": message_ts}

    except Exception as e:
        print(f"[SLACK] Error sending approval DM: {e}")
        return {"success": False}


def update_approval_dm(token: str, channel_id: str, message_ts: str, decision_id: str,
                       decision_number: int, title: str, status: str, approver_name: str,
                       comment: str = None) -> bool:
    """Update an approval DM to show the decision was already acted upon.

    Returns True if updated successfully.
    """
    decision_url = f"https://imputable.vercel.app/decisions/{decision_id}"

    if status == "approved":
        emoji = "✅"
        status_text = "Approved"
    else:
        emoji = "❌"
        status_text = "Rejected"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{emoji} {status_text}", "emoji": True}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<{decision_url}|DECISION-{decision_number}: {title}>*"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{approver_name}* {status} this decision."
            }
        },
    ]

    if comment:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"_Reason: {comment}_"}
        })

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Decision", "emoji": True},
                "url": decision_url,
                "action_id": "view_decision",
            },
        ]
    })

    # Update the message
    update_url = "https://slack.com/api/chat.update"
    update_payload = json.dumps({
        "channel": channel_id,
        "ts": message_ts,
        "text": f"DECISION-{decision_number} has been {status}",
        "blocks": blocks
    }).encode()
    update_req = urllib.request.Request(update_url, data=update_payload, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    })

    try:
        update_response = urllib.request.urlopen(update_req, timeout=5)
        update_data = json.loads(update_response.read().decode())
        if not update_data.get("ok"):
            print(f"[SLACK] Error updating approval DM: {update_data.get('error')}")
            return False
        print(f"[SLACK] Updated approval DM for DECISION-{decision_number}")
        return True
    except Exception as e:
        print(f"[SLACK] Error updating approval DM: {e}")
        return False


_db_engine = None

def get_db_connection():
    """Get database connection with connection pooling."""
    global _db_engine
    if _db_engine is not None:
        return _db_engine

    from sqlalchemy import create_engine
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        return None

    # Use NullPool for serverless (no persistent connections)
    # But with fast connect settings
    from sqlalchemy.pool import NullPool
    _db_engine = create_engine(
        db_url,
        connect_args={
            "sslmode": "require",
            "connect_timeout": 5,
        },
        poolclass=NullPool,
    )
    return _db_engine


def decrypt_token(encrypted: str) -> str:
    """Decrypt a stored token."""
    encryption_key = os.environ.get("ENCRYPTION_KEY", "")
    if not encryption_key:
        return encrypted
    try:
        from cryptography.fernet import Fernet
        f = Fernet(encryption_key.encode())
        return f.decrypt(encrypted.encode()).decode()
    except Exception:
        return encrypted


def verify_slack_signature(body: bytes, timestamp: str, signature: str) -> bool:
    """Verify Slack request signature."""
    signing_secret = os.environ.get("SLACK_SIGNING_SECRET", "")
    if not signing_secret:
        return False

    # Check timestamp (5 min window)
    try:
        if abs(time.time() - int(timestamp)) > 300:
            return False
    except ValueError:
        return False

    sig_basestring = f"v0:{timestamp}:{body.decode()}"
    expected = "v0=" + hmac.new(
        signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


# =============================================================================
# SLACK BLOCKS & MODALS
# =============================================================================

class SlackBlocks:
    """Slack Block Kit builders."""

    @staticmethod
    def main_menu(org_name: str = "your organization"):
        return [
            {"type": "header", "text": {"type": "plain_text", "text": "Imputable", "emoji": True}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"Decision ledger for *{org_name}*"}},
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Quick Actions*"}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "New Decision", "emoji": True}, "style": "primary", "action_id": "open_create_decision_modal"},
                {"type": "button", "text": {"type": "plain_text", "text": "View Decisions", "emoji": True}, "action_id": "list_decisions"},
                {"type": "button", "text": {"type": "plain_text", "text": "Help", "emoji": True}, "action_id": "show_help"}
            ]}
        ]

    @staticmethod
    def help_message():
        return [
            {"type": "header", "text": {"type": "plain_text", "text": "Imputable Commands", "emoji": True}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Available Commands:*\n\n`/decision` - Show main menu\n`/decision add <title>` - Create a new decision\n`/decision list` - View recent decisions\n`/decision search <query>` - Search decisions\n`/decision poll <question>` - Start consensus poll\n`/decision log` - AI-analyze recent conversation and log as decision\n`/decision log <topic>` - Same, but focused on a specific topic\n`/decision help` - Show this help"}},
            {"type": "divider"},
            {"type": "context", "elements": [{"type": "mrkdwn", "text": "You can also right-click any message and select *Log as Decision* to capture it."}]}
        ]

    @staticmethod
    def search_results(query: str, decisions: list):
        if not decisions:
            return [
                {"type": "section", "text": {"type": "mrkdwn", "text": f"No decisions found matching *{query}*"}}
            ]

        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": f"*Search results for:* {query}"}}]

        status_emoji = {"draft": ":white_circle:", "pending_review": ":large_yellow_circle:", "approved": ":large_green_circle:", "deprecated": ":red_circle:", "superseded": ":black_circle:"}

        for d in decisions[:5]:
            dec_id, dec_num, title, status = d
            emoji = status_emoji.get(status, ":white_circle:")
            frontend_url = os.environ.get("FRONTEND_URL", "https://imputable.vercel.app")
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"{emoji} *<{frontend_url}/decisions/{dec_id}|DECISION-{dec_num}>*\n{title}"},
                "accessory": {"type": "button", "text": {"type": "plain_text", "text": "View"}, "url": f"{frontend_url}/decisions/{dec_id}"}
            })

        return blocks

    @staticmethod
    def consensus_poll(decision_id: str, decision_number: int, title: str, votes: dict, decision_status: str = "pending_review", channel_member_count: int = 0, creator_id: str = "", created_at: str = ""):
        agree = votes.get("agree", [])
        concern = votes.get("concern", [])
        block = votes.get("block", [])
        total = len(agree) + len(concern) + len(block)

        frontend_url = os.environ.get("FRONTEND_URL", "https://imputable.vercel.app")

        # Dynamic threshold based on channel size (~60% of members, min 2, max 10)
        import math
        if channel_member_count > 0:
            threshold = max(2, min(10, math.ceil(channel_member_count * 0.6)))
        else:
            threshold = 3  # Fallback if channel size unknown

        # Smart threshold detection
        # Consensus reached: threshold agrees with no blocks
        # Blocked: Any blocks present
        # Concerns: Has concerns but no blocks
        consensus_reached = len(agree) >= threshold and len(block) == 0
        is_blocked = len(block) > 0
        has_concerns = len(concern) > 0 and not is_blocked

        # Determine status text
        if decision_status == "approved":
            status_text = ":white_check_mark: *Decision Approved*"
            status_emoji = ":large_green_circle:"
        elif is_blocked:
            status_text = f":no_entry: *Blocked* - {len(block)} team member{'s' if len(block) > 1 else ''} blocked this decision"
            status_emoji = ":red_circle:"
        elif consensus_reached:
            status_text = ":tada: *Consensus Reached!*"
            status_emoji = ":large_green_circle:"
        elif has_concerns:
            status_text = f":warning: *{len(concern)} concern{'s' if len(concern) > 1 else ''}* - Discussion may be needed"
            status_emoji = ":large_yellow_circle:"
        else:
            remaining = threshold - len(agree)
            if remaining > 0:
                status_text = f"*Consensus Poll* - {len(agree)}/{threshold} agrees needed"
            else:
                status_text = f"*Consensus Poll* - {total} vote{'s' if total != 1 else ''}"
            status_emoji = ":white_circle:"

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": f"{title[:75]}", "emoji": True}},
            {"type": "section", "text": {"type": "mrkdwn", "text": status_text}},
        ]

        # Only show voting buttons if not approved
        if decision_status != "approved":
            blocks.append({"type": "actions", "block_id": f"poll_{decision_id}", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": f"Agree ({len(agree)})", "emoji": True}, "style": "primary", "action_id": "poll_vote_agree", "value": decision_id},
                {"type": "button", "text": {"type": "plain_text", "text": f"Concern ({len(concern)})", "emoji": True}, "action_id": "poll_vote_concern", "value": decision_id},
                {"type": "button", "text": {"type": "plain_text", "text": f"Block ({len(block)})", "emoji": True}, "style": "danger", "action_id": "poll_vote_block", "value": decision_id}
            ]})

        # Show who voted
        vote_texts = []
        if agree:
            vote_texts.append(f":white_check_mark: {', '.join(agree)}")
        if concern:
            vote_texts.append(f":warning: {', '.join(concern)}")
        if block:
            vote_texts.append(f":no_entry: {', '.join(block)}")

        if vote_texts:
            blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": " | ".join(vote_texts)}]})

        # Show consensus reached prompt with action button (only if not already approved)
        # Include creator_id in value so we can verify on click
        if consensus_reached and not is_blocked and decision_status != "approved":
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": ":rocket: *Ready to make it official?*\nThe team has reached consensus. Only the poll creator can approve."},
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve Decision", "emoji": True},
                    "style": "primary",
                    "action_id": "poll_approve_decision",
                    "value": f"{decision_id}|{creator_id}"
                }
            })

        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"{status_emoji} <{frontend_url}/decisions/{decision_id}|View full decision>"}]})

        return blocks

    @staticmethod
    def semantic_search_results(query: str, decisions: list, explanation: str = "", best_match: str = ""):
        """Format AI-powered semantic search results."""
        frontend_url = os.environ.get("FRONTEND_URL", "https://imputable.vercel.app")

        if not decisions:
            blocks = [
                {"type": "section", "text": {"type": "mrkdwn", "text": f":mag: *Search:* {query}"}},
                {"type": "section", "text": {"type": "mrkdwn", "text": explanation or "No matching decisions found. Try different keywords or check `/decision list` for recent decisions."}}
            ]
            return blocks

        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f":mag: *Search:* {query}"}}
        ]

        # Add AI explanation if provided
        if explanation:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"_{explanation}_"}})

        # Add best match summary if provided
        if best_match:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f":bulb: *Best match:* {best_match}"}})

        blocks.append({"type": "divider"})

        status_emoji = {"draft": ":white_circle:", "pending_review": ":large_yellow_circle:", "approved": ":large_green_circle:", "deprecated": ":red_circle:", "superseded": ":black_circle:"}

        for d in decisions[:5]:
            dec_id, dec_num, title, status = d
            emoji = status_emoji.get(status, ":white_circle:")
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"{emoji} *<{frontend_url}/decisions/{dec_id}|DECISION-{dec_num}>*\n{title}"},
                "accessory": {"type": "button", "text": {"type": "plain_text", "text": "View"}, "url": f"{frontend_url}/decisions/{dec_id}", "action_id": f"view_decision_{dec_id}"}
            })

        return blocks

    @staticmethod
    def decision_created(decision_id: str, decision_number: int, title: str):
        frontend_url = os.environ.get("FRONTEND_URL", "https://imputable.vercel.app")
        return [
            {"type": "section", "text": {"type": "mrkdwn", "text": f":white_check_mark: *Decision logged*\n*<{frontend_url}/decisions/{decision_id}|DECISION-{decision_number}>*: {title}"}}
        ]

    @staticmethod
    def duplicate_warning(decision_id: str, decision_number: int, title: str):
        frontend_url = os.environ.get("FRONTEND_URL", "https://imputable.vercel.app")
        return [
            {"type": "section", "text": {"type": "mrkdwn", "text": f":warning: This message was already logged as *<{frontend_url}/decisions/{decision_id}|DECISION-{decision_number}>*: {title}"}}
        ]


class SlackModals:
    """Slack modal builders."""

    @staticmethod
    def create_decision(prefill_title: str = "", prefill_context: str = ""):
        return {
            "type": "modal",
            "callback_id": "create_decision_modal",
            "title": {"type": "plain_text", "text": "New Decision"},
            "submit": {"type": "plain_text", "text": "Create"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {"type": "input", "block_id": "title_block", "element": {"type": "plain_text_input", "action_id": "title_input", "initial_value": prefill_title, "placeholder": {"type": "plain_text", "text": "What was decided?"}}, "label": {"type": "plain_text", "text": "Decision Title"}},
                {"type": "input", "block_id": "context_block", "element": {"type": "plain_text_input", "action_id": "context_input", "multiline": True, "initial_value": prefill_context, "placeholder": {"type": "plain_text", "text": "What led to this decision?"}}, "label": {"type": "plain_text", "text": "Context"}, "optional": True},
                {"type": "input", "block_id": "choice_block", "element": {"type": "plain_text_input", "action_id": "choice_input", "multiline": True, "placeholder": {"type": "plain_text", "text": "Describe the decision"}}, "label": {"type": "plain_text", "text": "Decision"}},
                {"type": "input", "block_id": "rationale_block", "element": {"type": "plain_text_input", "action_id": "rationale_input", "multiline": True, "placeholder": {"type": "plain_text", "text": "Why this choice?"}}, "label": {"type": "plain_text", "text": "Rationale"}, "optional": True},
                {"type": "input", "block_id": "impact_block", "element": {"type": "static_select", "action_id": "impact_select", "initial_option": {"text": {"type": "plain_text", "text": "Medium"}, "value": "medium"}, "options": [
                    {"text": {"type": "plain_text", "text": "Low"}, "value": "low"},
                    {"text": {"type": "plain_text", "text": "Medium"}, "value": "medium"},
                    {"text": {"type": "plain_text", "text": "High"}, "value": "high"},
                    {"text": {"type": "plain_text", "text": "Critical"}, "value": "critical"}
                ]}, "label": {"type": "plain_text", "text": "Impact Level"}}
            ]
        }

    @staticmethod
    def log_message(prefill_title: str, message_text: str, channel_id: str, message_ts: str, thread_ts: str = None):
        metadata = json.dumps({"channel_id": channel_id, "message_ts": message_ts, "thread_ts": thread_ts, "ai_generated": False})
        return {
            "type": "modal",
            "callback_id": "log_message_modal",
            "private_metadata": metadata,
            "title": {"type": "plain_text", "text": "Log as Decision"},
            "submit": {"type": "plain_text", "text": "Log Decision"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {"type": "context", "elements": [{"type": "mrkdwn", "text": f"_Original message:_\n>{message_text[:500]}{'...' if len(message_text) > 500 else ''}"}]},
                {"type": "divider"},
                {"type": "input", "block_id": "title_block", "element": {"type": "plain_text_input", "action_id": "title_input", "initial_value": prefill_title[:150], "placeholder": {"type": "plain_text", "text": "Decision title"}}, "label": {"type": "plain_text", "text": "Title"}},
                {"type": "input", "block_id": "context_block", "element": {"type": "plain_text_input", "action_id": "context_input", "multiline": True, "placeholder": {"type": "plain_text", "text": "Additional context"}}, "label": {"type": "plain_text", "text": "Context"}, "optional": True},
                {"type": "input", "block_id": "impact_block", "element": {"type": "static_select", "action_id": "impact_select", "initial_option": {"text": {"type": "plain_text", "text": "Medium"}, "value": "medium"}, "options": [
                    {"text": {"type": "plain_text", "text": "Low"}, "value": "low"},
                    {"text": {"type": "plain_text", "text": "Medium"}, "value": "medium"},
                    {"text": {"type": "plain_text", "text": "High"}, "value": "high"},
                    {"text": {"type": "plain_text", "text": "Critical"}, "value": "critical"}
                ]}, "label": {"type": "plain_text", "text": "Impact Level"}}
            ]
        }

    @staticmethod
    def ai_prefilled_modal(analysis: dict, channel_id: str, message_ts: str, thread_ts: str = None):
        """Build modal pre-filled with AI-analyzed decision content."""
        # Ensure analysis is a dict
        if not isinstance(analysis, dict):
            analysis = {}

        # Format alternatives
        alternatives_text = ""
        alternatives = analysis.get("alternatives", [])
        if alternatives and isinstance(alternatives, list):
            alt_lines = []
            for alt in alternatives[:5]:
                if isinstance(alt, dict):
                    alt_lines.append(f"- {alt.get('name', 'Unknown')}: {alt.get('rejected_reason', 'No reason given')}")
            alternatives_text = "\n".join(alt_lines)

        # Confidence display
        confidence = analysis.get("confidence_score", 0.5)
        confidence_pct = int(confidence * 100)
        if confidence_pct >= 80:
            confidence_emoji = ":white_check_mark:"
            confidence_text = "High confidence"
        elif confidence_pct >= 50:
            confidence_emoji = ":large_yellow_circle:"
            confidence_text = "Medium confidence"
        else:
            confidence_emoji = ":warning:"
            confidence_text = "Low confidence - please review carefully"

        # Dissenters and deadlines
        dissenters = ", ".join(analysis.get("key_dissenters", [])[:5]) or "None identified"
        deadlines = ", ".join(analysis.get("deadlines", [])[:3]) or "None mentioned"

        metadata = json.dumps({
            "channel_id": channel_id,
            "message_ts": message_ts,
            "thread_ts": thread_ts,
            "ai_generated": True,
            "confidence_score": confidence,
            "suggested_status": analysis.get("suggested_status", "draft")
        })

        impact_value = analysis.get("suggested_impact", "medium")
        impact_options = [
            {"text": {"type": "plain_text", "text": "Low"}, "value": "low"},
            {"text": {"type": "plain_text", "text": "Medium"}, "value": "medium"},
            {"text": {"type": "plain_text", "text": "High"}, "value": "high"},
            {"text": {"type": "plain_text", "text": "Critical"}, "value": "critical"}
        ]
        initial_impact = next((o for o in impact_options if o["value"] == impact_value), impact_options[1])

        return {
            "type": "modal",
            "callback_id": "log_message_modal",
            "private_metadata": metadata,
            "title": {"type": "plain_text", "text": "AI Decision Draft"},
            "submit": {"type": "plain_text", "text": "Save to Imputable"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn", "text": f"{confidence_emoji} *AI Analysis Complete* ({confidence_pct}% confidence)\n_{confidence_text}_"}},
                {"type": "divider"},
                {"type": "input", "block_id": "title_block", "element": {"type": "plain_text_input", "action_id": "title_input", "initial_value": analysis.get("title", "")[:150], "placeholder": {"type": "plain_text", "text": "Decision title"}}, "label": {"type": "plain_text", "text": "Title"}},
                {"type": "input", "block_id": "context_block", "element": {"type": "plain_text_input", "action_id": "context_input", "multiline": True, "initial_value": analysis.get("context", "")[:3000], "placeholder": {"type": "plain_text", "text": "Background and problem"}}, "label": {"type": "plain_text", "text": "Context"}, "optional": True},
                {"type": "input", "block_id": "choice_block", "element": {"type": "plain_text_input", "action_id": "choice_input", "multiline": True, "initial_value": analysis.get("choice", "")[:3000], "placeholder": {"type": "plain_text", "text": "What was decided"}}, "label": {"type": "plain_text", "text": "Decision"}},
                {"type": "input", "block_id": "rationale_block", "element": {"type": "plain_text_input", "action_id": "rationale_input", "multiline": True, "initial_value": analysis.get("rationale", "")[:3000], "placeholder": {"type": "plain_text", "text": "Why this choice"}}, "label": {"type": "plain_text", "text": "Rationale"}, "optional": True},
                {"type": "input", "block_id": "alternatives_block", "element": {"type": "plain_text_input", "action_id": "alternatives_input", "multiline": True, "initial_value": alternatives_text[:3000], "placeholder": {"type": "plain_text", "text": "- Option: Reason rejected"}}, "label": {"type": "plain_text", "text": "Alternatives Considered"}, "optional": True},
                {"type": "input", "block_id": "impact_block", "element": {"type": "static_select", "action_id": "impact_select", "initial_option": initial_impact, "options": impact_options}, "label": {"type": "plain_text", "text": "Impact Level"}},
                {"type": "divider"},
                {"type": "context", "elements": [{"type": "mrkdwn", "text": f":busts_in_silhouette: *Key Dissenters:* {dissenters}"}]},
                {"type": "context", "elements": [{"type": "mrkdwn", "text": f":calendar: *Deadlines:* {deadlines}"}]},
                {"type": "context", "elements": [{"type": "mrkdwn", "text": f":sparkles: *Suggested Status:* {analysis.get('suggested_status', 'draft').replace('_', ' ').title()}"}]}
            ]
        }


# =============================================================================
# SLACK HANDLERS
# =============================================================================

def handle_slack_command(form_data: dict, conn) -> dict:
    """Handle /decisions slash command."""
    from sqlalchemy import text

    team_id = form_data.get("team_id", "")
    channel_id = form_data.get("channel_id", "")
    user_id = form_data.get("user_id", "")
    user_name = form_data.get("user_name", "")
    trigger_id = form_data.get("trigger_id", "")
    cmd_text = form_data.get("text", "").strip()

    # Get org
    result = conn.execute(text("SELECT id, name, slack_access_token FROM organizations WHERE slack_team_id = :team_id"), {"team_id": team_id})
    org = result.fetchone()

    if not org:
        return {"response_type": "ephemeral", "text": ":warning: This workspace is not connected to Imputable."}

    org_id, org_name, slack_token = org[0], org[1], org[2]

    # Check if user is active in the organization
    result = conn.execute(text("""
        SELECT om.status, om.role, u.id
        FROM users u
        JOIN organization_members om ON om.user_id = u.id AND om.organization_id = :org_id
        WHERE u.slack_user_id = :slack_id AND u.deleted_at IS NULL
    """), {"org_id": org_id, "slack_id": user_id})
    member_row = result.fetchone()

    if member_row:
        member_status, member_role, db_user_id = member_row[0] or "active", member_row[1], member_row[2]
        if member_status == "inactive":
            return {
                "response_type": "ephemeral",
                "text": ":no_entry: *You don't have an active seat on Imputable.*\n\nYour organization is on a limited plan and your account is inactive. Ask your admin to activate your account or upgrade the plan.",
                "blocks": [
                    {"type": "section", "text": {"type": "mrkdwn", "text": ":no_entry: *You don't have an active seat on Imputable.*"}},
                    {"type": "section", "text": {"type": "mrkdwn", "text": "Your organization is on a limited plan and your account is inactive.\n\n*To use Imputable:*\n1. Ask your organization admin to activate your account, or\n2. Ask them to upgrade to Pro for unlimited members"}},
                    {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Organization: {org_name}"}]}
                ]
            }
    else:
        # User not in DB - they need to be imported/activated by an admin first
        # This prevents bypassing the plan limits by having new Slack users auto-create accounts
        return {
            "response_type": "ephemeral",
            "text": ":wave: *Welcome to Imputable!*\n\nYou're not yet a member of this organization's Imputable workspace. Please ask your organization admin to add you as a member.",
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn", "text": ":wave: *Welcome to Imputable!*"}},
                {"type": "section", "text": {"type": "mrkdwn", "text": "You're not yet a member of this organization's Imputable workspace.\n\n*To get access:*\n1. Ask your organization admin to add you as a member\n2. They can do this from the Team settings in Imputable"}},
                {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Organization: {org_name}"}]}
            ]
        }

    # Parse command
    cmd_lower = cmd_text.lower()

    # Help
    if cmd_lower in ("help", "?"):
        return {"response_type": "ephemeral", "blocks": SlackBlocks.help_message()}

    # List
    if cmd_lower in ("list", "show", "recent"):
        result = conn.execute(text("""
            SELECT d.id, d.decision_number, dv.title, d.status
            FROM decisions d
            JOIN decision_versions dv ON d.current_version_id = dv.id
            WHERE d.organization_id = :org_id AND d.deleted_at IS NULL
            ORDER BY d.created_at DESC LIMIT 5
        """), {"org_id": org_id})
        decisions = result.fetchall()
        return {"response_type": "ephemeral", "blocks": SlackBlocks.search_results("recent decisions", decisions)}

    # Search (AI-powered semantic search)
    if cmd_lower.startswith("search "):
        query = cmd_text[7:].strip()

        # First, fetch all decisions for semantic search
        result = conn.execute(text("""
            SELECT d.id, d.decision_number, dv.title, d.status, dv.content, d.created_at
            FROM decisions d
            JOIN decision_versions dv ON d.current_version_id = dv.id
            WHERE d.organization_id = :org_id AND d.deleted_at IS NULL
            ORDER BY d.created_at DESC LIMIT 50
        """), {"org_id": org_id})
        all_decisions = result.fetchall()

        if not all_decisions:
            return {"response_type": "ephemeral", "text": ":mag: No decisions found in your organization yet."}

        # Convert to list of dicts for semantic search
        decisions_for_search = []
        decisions_by_id = {}
        for row in all_decisions:
            d = {
                "id": str(row[0]),
                "decision_number": row[1],
                "title": row[2],
                "status": row[3],
                "content": row[4],
                "created_at": str(row[5]) if row[5] else ""
            }
            decisions_for_search.append(d)
            decisions_by_id[str(row[0])] = d

        # Use AI to find relevant decisions
        search_result = semantic_search_decisions(query, decisions_for_search)

        matched_ids = search_result.get("matches", [])
        explanation = search_result.get("explanation", "")
        best_match = search_result.get("best_match_summary", "")

        if not matched_ids:
            return {"response_type": "ephemeral", "blocks": SlackBlocks.semantic_search_results(query, [], explanation)}

        # Get matched decisions in order
        matched_decisions = []
        for mid in matched_ids:
            if mid in decisions_by_id:
                d = decisions_by_id[mid]
                matched_decisions.append((d["id"], d["decision_number"], d["title"], d["status"]))

        return {"response_type": "ephemeral", "blocks": SlackBlocks.semantic_search_results(query, matched_decisions, explanation, best_match)}

    # Poll
    if cmd_lower.startswith("poll "):
        question = cmd_text[5:].strip()

        # Check if referencing existing decision (DECISION-123)
        dec_match = re.match(r"^DECISION-(\d+)\s*(.*)$", question, re.IGNORECASE)
        decision_status = "pending_review"  # Default for new decisions

        if dec_match:
            decision_number = int(dec_match.group(1))
            result = conn.execute(text("""
                SELECT d.id, d.decision_number, dv.title, d.status
                FROM decisions d
                JOIN decision_versions dv ON d.current_version_id = dv.id
                WHERE d.organization_id = :org_id AND d.decision_number = :num
            """), {"org_id": org_id, "num": decision_number})
            dec = result.fetchone()

            if not dec:
                return {"response_type": "ephemeral", "text": f":warning: Decision DECISION-{decision_number} not found."}

            decision_id, decision_number, title, decision_status = str(dec[0]), dec[1], dec[2], dec[3]
        else:
            # Verify user is an active member before creating poll
            db_user_id, member_status, error_msg = get_active_member_user_id(conn, org_id, user_id)
            if not db_user_id:
                return {"response_type": "ephemeral", "text": f":warning: {error_msg}"}

            # Create new decision from question
            result = conn.execute(text("SELECT COALESCE(MAX(decision_number), 0) + 1 FROM decisions WHERE organization_id = :org_id"), {"org_id": org_id})
            next_num = result.fetchone()[0]

            decision_id = str(uuid4())
            version_id = str(uuid4())

            # Get channel member count for dynamic threshold
            channel_member_count = 0
            if slack_token:
                token = decrypt_token(slack_token)
                try:
                    members_req = urllib.request.Request(
                        f"https://slack.com/api/conversations.members?channel={channel_id}&limit=100",
                        headers={"Authorization": f"Bearer {token}"}
                    )
                    members_resp = urllib.request.urlopen(members_req, timeout=5)
                    members_data = json.loads(members_resp.read().decode())
                    if members_data.get("ok"):
                        channel_member_count = len(members_data.get("members", []))
                except Exception as e:
                    print(f"[SLACK POLL] Failed to get channel members: {e}")

            conn.execute(text("""
                INSERT INTO decisions (id, organization_id, decision_number, status, created_by, source, slack_channel_id, is_temporary, created_at, updated_at)
                VALUES (:id, :org_id, :num, 'pending_review', :user_id, 'slack', :channel_id, false, NOW(), NOW())
            """), {"id": decision_id, "org_id": org_id, "num": next_num, "user_id": db_user_id, "channel_id": channel_id})

            content = json.dumps({"context": "This decision was proposed via Slack poll for team consensus.", "choice": f"Team is voting on: {question}", "rationale": None, "alternatives": []})
            tags = '{"slack-logged", "poll"}'
            custom_fields = json.dumps({"channel_member_count": channel_member_count, "poll_creator_slack_id": user_id})
            conn.execute(text("""
                INSERT INTO decision_versions (id, decision_id, version_number, title, impact_level, content, tags, created_by, created_at, custom_fields)
                VALUES (:id, :did, 1, :title, 'medium', :content, :tags, :user_id, NOW(), :custom_fields)
            """), {"id": version_id, "did": decision_id, "title": question[:255], "content": content, "tags": tags, "user_id": db_user_id, "custom_fields": custom_fields})

            conn.execute(text("UPDATE decisions SET current_version_id = :vid WHERE id = :did"), {"vid": version_id, "did": decision_id})
            conn.commit()

            decision_number = next_num
            title = question[:255]

        # Get current votes and custom_fields
        result = conn.execute(text("""
            SELECT vote_type, external_user_name FROM poll_votes WHERE decision_id = :did
        """), {"did": decision_id})

        votes = {"agree": [], "concern": [], "block": []}
        for row in result.fetchall():
            vote_type, name = row[0], row[1] or "Someone"
            if vote_type in votes:
                votes[vote_type].append(name)

        # Get channel_member_count and creator from custom_fields
        channel_member_count = 0
        creator_slack_id = user_id  # Default to current user for new polls
        result = conn.execute(text("""
            SELECT dv.custom_fields FROM decision_versions dv
            JOIN decisions d ON d.current_version_id = dv.id
            WHERE d.id = :did
        """), {"did": decision_id})
        cf_row = result.fetchone()
        if cf_row and cf_row[0]:
            cf = cf_row[0] if isinstance(cf_row[0], dict) else json.loads(cf_row[0]) if cf_row[0] else {}
            channel_member_count = cf.get("channel_member_count", 0)
            creator_slack_id = cf.get("poll_creator_slack_id", user_id)

        return {"response_type": "in_channel", "blocks": SlackBlocks.consensus_poll(decision_id, decision_number, title, votes, decision_status, channel_member_count, creator_slack_id)}

    # Add/create
    if cmd_lower.startswith(("add ", "create ", "new ")):
        prefill = cmd_text.split(" ", 1)[1] if " " in cmd_text else ""

        if slack_token and trigger_id:
            token = decrypt_token(slack_token)
            modal = SlackModals.create_decision(prefill_title=prefill)

            payload = json.dumps({"trigger_id": trigger_id, "view": modal}).encode()
            req = urllib.request.Request(
                "https://slack.com/api/views.open",
                data=payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            )
            try:
                urllib.request.urlopen(req, timeout=10)
            except Exception:
                pass

        return {"response_type": "ephemeral", "text": ":pencil: Opening decision form..."}

    # Log - AI-powered logging of recent conversation
    if cmd_lower == "log" or cmd_lower.startswith("log "):
        hint = cmd_text[4:].strip() if cmd_lower.startswith("log ") else ""

        if not slack_token or not trigger_id:
            return {"response_type": "ephemeral", "text": ":warning: Unable to open form. Please try again."}

        token = decrypt_token(slack_token)

        # Open loading modal immediately (trigger_id expires in 3 seconds)
        loading_modal = {
            "type": "modal",
            "callback_id": "ai_loading_modal",
            "title": {"type": "plain_text", "text": "Analyzing..."},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn", "text": ":sparkles: *AI is analyzing the recent conversation...*\n\nThis may take a few seconds."}}
            ]
        }

        view_id = None
        payload_data = json.dumps({"trigger_id": trigger_id, "view": loading_modal}).encode()
        req = urllib.request.Request(
            "https://slack.com/api/views.open",
            data=payload_data,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )
        try:
            resp = urllib.request.urlopen(req, timeout=5)
            resp_data = json.loads(resp.read().decode())
            if resp_data.get("ok"):
                view_id = resp_data.get("view", {}).get("id")
        except Exception as e:
            print(f"[SLACK LOG CMD] Failed to open loading modal: {e}")
            return {"response_type": "ephemeral", "text": ":warning: Failed to open form. Please try again."}

        # Fetch recent channel messages
        try:
            messages = fetch_recent_channel_messages(token, channel_id, limit=50)
            if not messages:
                # Update modal with error
                if view_id:
                    error_modal = {
                        "type": "modal",
                        "callback_id": "log_error_modal",
                        "title": {"type": "plain_text", "text": "No Messages"},
                        "close": {"type": "plain_text", "text": "Close"},
                        "blocks": [
                            {"type": "section", "text": {"type": "mrkdwn", "text": ":warning: No recent messages found in this channel to analyze."}}
                        ]
                    }
                    update_data = json.dumps({"view_id": view_id, "view": error_modal}).encode()
                    req = urllib.request.Request(
                        "https://slack.com/api/views.update",
                        data=update_data,
                        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                    )
                    try:
                        urllib.request.urlopen(req, timeout=10)
                    except Exception:
                        pass
                return {"response_type": "ephemeral", "text": ""}

            messages = resolve_slack_user_names(token, messages)

            # Get channel name for context
            channel_name = ""
            try:
                channel_info_url = f"https://slack.com/api/conversations.info?channel={channel_id}"
                req = urllib.request.Request(channel_info_url, headers={"Authorization": f"Bearer {token}"})
                resp = urllib.request.urlopen(req, timeout=5)
                channel_data = json.loads(resp.read().decode())
                if channel_data.get("ok"):
                    channel_name = channel_data.get("channel", {}).get("name", "")
            except Exception:
                pass

            # Analyze with AI (pass hint if provided)
            gemini_key = os.environ.get("GEMINI_API_KEY", "")
            analysis = None
            if gemini_key:
                analysis = analyze_with_gemini(messages, channel_name, hint=hint if hint else None)

            # Build modal
            if analysis:
                # Use the most recent message timestamp for metadata
                latest_ts = messages[-1].get("timestamp", "") if messages else ""
                modal = SlackModals.ai_prefilled_modal(analysis, channel_id, latest_ts, None)
            else:
                prefill_title = hint if hint else "Decision from recent conversation"
                modal = SlackModals.log_message(prefill_title, "", channel_id, "", None)

            # Update modal with results
            if view_id:
                update_data = json.dumps({"view_id": view_id, "view": modal}).encode()
                req = urllib.request.Request(
                    "https://slack.com/api/views.update",
                    data=update_data,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                )
                try:
                    urllib.request.urlopen(req, timeout=10)
                except Exception as e:
                    print(f"[SLACK LOG CMD] Failed to update modal: {e}")

        except Exception as e:
            print(f"[SLACK LOG CMD] Error: {e}")
            # Update modal with error
            if view_id:
                error_modal = {
                    "type": "modal",
                    "callback_id": "log_error_modal",
                    "title": {"type": "plain_text", "text": "Error"},
                    "close": {"type": "plain_text", "text": "Close"},
                    "blocks": [
                        {"type": "section", "text": {"type": "mrkdwn", "text": f":warning: An error occurred while analyzing the conversation. Please try again."}}
                    ]
                }
                update_data = json.dumps({"view_id": view_id, "view": error_modal}).encode()
                req = urllib.request.Request(
                    "https://slack.com/api/views.update",
                    data=update_data,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                )
                try:
                    urllib.request.urlopen(req, timeout=10)
                except Exception:
                    pass

        return {"response_type": "ephemeral", "text": ""}

    # Default: show menu
    return {"response_type": "ephemeral", "blocks": SlackBlocks.main_menu(org_name)}


def handle_slack_interactions(payload: dict, conn) -> dict:
    """Handle Slack interactive components."""
    from sqlalchemy import text

    interaction_type = payload.get("type")
    team_id = payload.get("team", {}).get("id")
    user = payload.get("user", {})
    user_id = user.get("id", "")
    user_name = user.get("username", "") or user.get("name", "")
    trigger_id = payload.get("trigger_id")

    # Get org
    result = conn.execute(text("SELECT id, slack_access_token FROM organizations WHERE slack_team_id = :team_id"), {"team_id": team_id})
    org = result.fetchone()

    if not org:
        return {}

    org_id, slack_token = str(org[0]), org[1]
    token = decrypt_token(slack_token) if slack_token else None

    # Check membership for interactions that require it
    # Note: poll_vote_* actions are intentionally exempt - anyone in Slack channel can vote
    # But poll_approve_decision and approve/reject_decision require membership
    needs_membership = False
    if interaction_type in ("message_action", "view_submission"):
        needs_membership = True
    elif interaction_type == "block_actions":
        actions = payload.get("actions", [])
        if actions:
            action_id = actions[0].get("action_id", "")
            # These actions require active membership
            if action_id in ("poll_approve_decision", "approve_decision", "reject_decision", "open_create_decision_modal"):
                needs_membership = True

    if needs_membership:
        db_user_id, member_status, error_msg = get_active_member_user_id(conn, org_id, user_id)
        if not db_user_id:
            # For view_submission, return error in modal
            if interaction_type == "view_submission":
                return {"response_action": "errors", "errors": {"title_block": error_msg}}
            # For block_actions, return ephemeral message
            if interaction_type == "block_actions":
                return {"response_type": "ephemeral", "text": f":warning: {error_msg}"}
            # For message_action, we can't show error easily, just return empty
            return {}

    # Message shortcut (Log as Decision) - AI-powered
    if interaction_type == "message_action":
        callback_id = payload.get("callback_id")

        if callback_id == "log_message_as_decision":
            message = payload.get("message", {})
            channel = payload.get("channel", {})

            message_text = message.get("text", "")
            message_ts = message.get("ts", "")
            thread_ts = message.get("thread_ts") or message_ts
            channel_id = channel.get("id", "")
            channel_name = channel.get("name", "")

            if not token:
                return {"response_type": "ephemeral", "text": ":x: Bot token not available."}

            # Open a loading modal IMMEDIATELY (trigger expires in 3 seconds!)
            loading_modal = {
                "type": "modal",
                "callback_id": "ai_loading_modal",
                "title": {"type": "plain_text", "text": "Analyzing..."},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": [
                    {"type": "section", "text": {"type": "mrkdwn", "text": ":sparkles: *AI is analyzing the conversation...*\n\nThis may take a few seconds."}}
                ]
            }

            view_id = None
            if trigger_id:
                payload_data = json.dumps({"trigger_id": trigger_id, "view": loading_modal}).encode()
                req = urllib.request.Request(
                    "https://slack.com/api/views.open",
                    data=payload_data,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                )
                try:
                    resp = urllib.request.urlopen(req, timeout=10)
                    resp_data = json.loads(resp.read().decode())
                    print(f"[SLACK] Loading modal response: ok={resp_data.get('ok')}, error={resp_data.get('error')}")
                    if resp_data.get("ok"):
                        view_id = resp_data.get("view", {}).get("id")
                except Exception as e:
                    print(f"[SLACK] Failed to open loading modal: {e}")
                    return {}

            # Now do the slow AI analysis
            try:
                gemini_key = os.environ.get("GEMINI_API_KEY", "")

                if gemini_key:
                    # Fetch messages for context
                    if thread_ts and thread_ts != message_ts:
                        # Message is in a thread - fetch the whole thread
                        messages = fetch_slack_thread(token, channel_id, thread_ts)
                    else:
                        # Not in a thread - fetch surrounding channel messages for context
                        messages = fetch_channel_context(token, channel_id, message_ts, count=25)
                        if not messages:
                            # Fallback to just the single message
                            messages = [{"author": message.get("user", "Unknown"), "text": message_text, "timestamp": message_ts}]

                    messages = resolve_slack_user_names(token, messages)
                    analysis = analyze_with_gemini(messages, channel_name)
                else:
                    analysis = None

                if analysis:
                    modal = SlackModals.ai_prefilled_modal(analysis, channel_id, message_ts, thread_ts)
                else:
                    prefill_title = message_text.split("\n")[0][:100] if message_text else "Decision from Slack"
                    modal = SlackModals.log_message(prefill_title, message_text, channel_id, message_ts, thread_ts)

                # Update the loading modal with the actual content
                if view_id:
                    payload_data = json.dumps({"view_id": view_id, "view": modal}).encode()
                    req = urllib.request.Request(
                        "https://slack.com/api/views.update",
                        data=payload_data,
                        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                    )
                    try:
                        resp = urllib.request.urlopen(req, timeout=10)
                        resp_data = json.loads(resp.read().decode())
                        print(f"[SLACK] views.update response: ok={resp_data.get('ok')}, error={resp_data.get('error')}")
                    except Exception as e:
                        print(f"[SLACK] Failed to update modal: {e}")

            except Exception as e:
                print(f"AI analysis error: {e}")
                # Update with fallback modal
                if view_id:
                    prefill_title = message_text.split("\n")[0][:100] if message_text else "Decision from Slack"
                    modal = SlackModals.log_message(prefill_title, message_text, channel_id, message_ts, thread_ts)
                    payload_data = json.dumps({"view_id": view_id, "view": modal}).encode()
                    req = urllib.request.Request(
                        "https://slack.com/api/views.update",
                        data=payload_data,
                        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                    )
                    try:
                        urllib.request.urlopen(req, timeout=10)
                    except Exception:
                        pass

            return {}

    # View submission (modal forms)
    if interaction_type == "view_submission":
        callback_id = payload.get("view", {}).get("callback_id")
        values = payload.get("view", {}).get("state", {}).get("values", {})

        if callback_id in ("create_decision_modal", "log_message_modal"):
            title = values.get("title_block", {}).get("title_input", {}).get("value", "").strip()
            context = values.get("context_block", {}).get("context_input", {}).get("value", "") or ""
            impact = values.get("impact_block", {}).get("impact_select", {}).get("selected_option", {}).get("value", "medium")

            if not title:
                return {"response_action": "errors", "errors": {"title_block": "Title is required"}}

            # For log_message_modal, get metadata
            metadata = {}
            if callback_id == "log_message_modal":
                try:
                    metadata = json.loads(payload.get("view", {}).get("private_metadata", "{}"))
                except:
                    pass

            choice = values.get("choice_block", {}).get("choice_input", {}).get("value", "") or context or title
            rationale = values.get("rationale_block", {}).get("rationale_input", {}).get("value", "") or ""

            # Parse alternatives from text format (for AI-generated modals)
            alternatives = []
            alternatives_text = values.get("alternatives_block", {}).get("alternatives_input", {}).get("value", "") or ""
            if alternatives_text:
                for line in alternatives_text.strip().split("\n"):
                    line = line.strip()
                    if line.startswith("- "):
                        line = line[2:]
                    if ": " in line:
                        name, reason = line.split(": ", 1)
                        alternatives.append({"name": name.strip(), "rejected_reason": reason.strip()})
                    elif line:
                        alternatives.append({"name": line, "rejected_reason": ""})

            # Check if AI-generated
            ai_generated = metadata.get("ai_generated", False)
            confidence_score = metadata.get("confidence_score", 0.0)
            suggested_status = metadata.get("suggested_status", "draft")

            # Verify user is an active member
            db_user_id, member_status, error_msg = get_active_member_user_id(conn, org_id, user_id)
            if not db_user_id:
                return {"response_action": "errors", "errors": {"title_block": error_msg}}

            # Get next decision number
            result = conn.execute(text("SELECT COALESCE(MAX(decision_number), 0) + 1 FROM decisions WHERE organization_id = :org_id"), {"org_id": org_id})
            next_num = result.fetchone()[0]

            decision_id = str(uuid4())
            version_id = str(uuid4())

            # Determine status - use AI suggestion if high confidence
            decision_status = "draft"
            if ai_generated and confidence_score >= 0.8 and suggested_status in ("draft", "pending_review", "approved"):
                decision_status = suggested_status

            # Create decision
            conn.execute(text("""
                INSERT INTO decisions (id, organization_id, decision_number, status, created_by, source, slack_channel_id, slack_message_ts, slack_thread_ts, is_temporary, created_at, updated_at)
                VALUES (:id, :org_id, :num, :status, :user_id, 'slack', :channel_id, :msg_ts, :thread_ts, false, NOW(), NOW())
            """), {
                "id": decision_id, "org_id": org_id, "num": next_num, "status": decision_status, "user_id": db_user_id,
                "channel_id": metadata.get("channel_id"), "msg_ts": metadata.get("message_ts"), "thread_ts": metadata.get("thread_ts")
            })

            content = json.dumps({"context": context, "choice": choice, "rationale": rationale, "alternatives": alternatives})

            # Build tags
            tags = ["slack-logged"]
            if ai_generated:
                tags.append("ai-generated")

            # Build custom_fields for AI metadata
            custom_fields = {}
            if ai_generated:
                custom_fields = {
                    "ai_generated": True,
                    "ai_confidence_score": confidence_score,
                    "verified_by_user": True,
                    "verified_by_slack_user_id": user_id
                }

            conn.execute(text("""
                INSERT INTO decision_versions (id, decision_id, version_number, title, impact_level, content, tags, created_by, created_at, custom_fields)
                VALUES (:id, :did, 1, :title, :impact, :content, :tags, :user_id, NOW(), :custom_fields)
            """), {
                "id": version_id, "did": decision_id, "title": title[:255], "impact": impact,
                "content": content, "tags": tags, "user_id": db_user_id,
                "custom_fields": json.dumps(custom_fields) if custom_fields else None
            })

            conn.execute(text("UPDATE decisions SET current_version_id = :vid WHERE id = :did"), {"vid": version_id, "did": decision_id})

            # Track logged message for duplicate detection (use thread_ts for AI to avoid duplicates)
            check_ts = metadata.get("thread_ts") or metadata.get("message_ts")
            if check_ts and metadata.get("channel_id"):
                conn.execute(text("""
                    INSERT INTO logged_messages (id, source, message_id, channel_id, decision_id, created_at)
                    VALUES (:id, 'slack', :msg_id, :channel_id, :did, NOW())
                    ON CONFLICT (source, message_id, channel_id) DO NOTHING
                """), {"id": str(uuid4()), "msg_id": check_ts, "channel_id": metadata.get("channel_id"), "did": decision_id})

            conn.commit()

            # Post confirmation to channel if we have one
            if token and metadata.get("channel_id"):
                msg_payload = json.dumps({
                    "channel": metadata.get("channel_id"),
                    "text": f"Decision logged: DECISION-{next_num}",
                    "blocks": SlackBlocks.decision_created(decision_id, next_num, title)
                }).encode()
                req = urllib.request.Request(
                    "https://slack.com/api/chat.postMessage",
                    data=msg_payload,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                )
                try:
                    urllib.request.urlopen(req, timeout=10)
                except Exception:
                    pass

            return {}

        # Handle reject decision modal submission
        if callback_id == "reject_decision_modal":
            reason = values.get("reason_block", {}).get("reason_input", {}).get("value", "").strip()

            # Get decision_id from metadata
            try:
                metadata = json.loads(payload.get("view", {}).get("private_metadata", "{}"))
            except:
                metadata = {}

            decision_id = metadata.get("decision_id", "")

            if not decision_id:
                return {"response_action": "errors", "errors": {"reason_block": "Decision not found"}}

            if not reason:
                return {"response_action": "errors", "errors": {"reason_block": "Please provide a reason for rejection"}}

            # Process the rejection
            result = handle_approval_action(conn, decision_id, user_id, user_name, "rejected", reason, payload)

            # For modal submissions, we return empty to close the modal
            # The handle_approval_action already updated the original DM message
            return {}

    # Block actions (button clicks)
    if interaction_type == "block_actions":
        actions = payload.get("actions", [])

        for action in actions:
            action_id = action.get("action_id", "")

            # Poll votes
            if action_id.startswith("poll_vote_"):
                vote_type = action_id.replace("poll_vote_", "")
                decision_id = action.get("value", "")

                if not decision_id or vote_type not in ("agree", "concern", "block"):
                    continue

                # Upsert vote
                result = conn.execute(text("""
                    SELECT id FROM poll_votes
                    WHERE decision_id = :did AND external_user_id = :uid AND source = 'slack'
                """), {"did": decision_id, "uid": user_id})
                existing = result.fetchone()

                if existing:
                    conn.execute(text("""
                        UPDATE poll_votes SET vote_type = :vote, external_user_name = :name, updated_at = NOW()
                        WHERE id = :id
                    """), {"vote": vote_type, "name": user_name, "id": existing[0]})
                else:
                    conn.execute(text("""
                        INSERT INTO poll_votes (id, decision_id, external_user_id, external_user_name, vote_type, source, created_at, updated_at)
                        VALUES (:id, :did, :uid, :name, :vote, 'slack', NOW(), NOW())
                    """), {"id": str(uuid4()), "did": decision_id, "uid": user_id, "name": user_name, "vote": vote_type})

                conn.commit()

                # Get updated votes and decision info
                result = conn.execute(text("""
                    SELECT d.decision_number, dv.title, d.status
                    FROM decisions d
                    JOIN decision_versions dv ON d.current_version_id = dv.id
                    WHERE d.id = :did
                """), {"did": decision_id})
                dec = result.fetchone()

                if dec:
                    result = conn.execute(text("SELECT vote_type, external_user_name FROM poll_votes WHERE decision_id = :did"), {"did": decision_id})
                    votes = {"agree": [], "concern": [], "block": []}
                    for row in result.fetchall():
                        vt, name = row[0], row[1] or "Someone"
                        if vt in votes:
                            votes[vt].append(name)

                    return {
                        "response_type": "in_channel",
                        "replace_original": True,
                        "blocks": SlackBlocks.consensus_poll(decision_id, dec[0], dec[1], votes, dec[2])
                    }

            # Approve decision from poll (consensus reached)
            if action_id == "poll_approve_decision":
                action_value = action.get("value", "")
                # Parse decision_id and creator_id from value (format: "decision_id|creator_id")
                if "|" in action_value:
                    decision_id, creator_id = action_value.split("|", 1)
                else:
                    decision_id = action_value
                    creator_id = ""

                if decision_id:
                    # Check if user is the poll creator
                    if creator_id and user_id != creator_id:
                        return {
                            "response_type": "ephemeral",
                            "replace_original": False,
                            "text": ":warning: Only the poll creator can approve this decision."
                        }

                    # Update decision status to approved
                    conn.execute(text("""
                        UPDATE decisions SET status = 'approved', updated_at = NOW()
                        WHERE id = :did AND status != 'approved'
                    """), {"did": decision_id})
                    conn.commit()

                    # Get updated decision info including custom_fields
                    result = conn.execute(text("""
                        SELECT d.decision_number, dv.title, d.status, dv.custom_fields
                        FROM decisions d
                        JOIN decision_versions dv ON d.current_version_id = dv.id
                        WHERE d.id = :did
                    """), {"did": decision_id})
                    dec = result.fetchone()

                    if dec:
                        # Get votes
                        result = conn.execute(text("SELECT vote_type, external_user_name FROM poll_votes WHERE decision_id = :did"), {"did": decision_id})
                        votes = {"agree": [], "concern": [], "block": []}
                        for row in result.fetchall():
                            vt, name = row[0], row[1] or "Someone"
                            if vt in votes:
                                votes[vt].append(name)

                        # Get channel_member_count and creator from custom_fields
                        channel_member_count = 0
                        creator_slack_id = creator_id or user_id
                        if dec[3]:
                            cf = dec[3] if isinstance(dec[3], dict) else json.loads(dec[3]) if dec[3] else {}
                            channel_member_count = cf.get("channel_member_count", 0)
                            creator_slack_id = cf.get("poll_creator_slack_id", creator_slack_id)

                        return {
                            "response_type": "in_channel",
                            "replace_original": True,
                            "blocks": SlackBlocks.consensus_poll(decision_id, dec[0], dec[1], votes, dec[2], channel_member_count, creator_slack_id)
                        }

            # Help button
            if action_id == "show_help":
                return {"response_type": "ephemeral", "blocks": SlackBlocks.help_message()}

            # Approve decision button (from DM)
            if action_id == "approve_decision":
                decision_id = action.get("value", "")
                if decision_id:
                    return handle_approval_action(conn, decision_id, user_id, user_name, "approved", None, payload)

            # Reject decision button (from DM) - opens modal for reason
            if action_id == "reject_decision":
                decision_id = action.get("value", "")
                trigger_id = payload.get("trigger_id", "")
                if decision_id and trigger_id and token:
                    # Open a modal to get rejection reason
                    modal = {
                        "type": "modal",
                        "callback_id": "reject_decision_modal",
                        "private_metadata": json.dumps({"decision_id": decision_id}),
                        "title": {"type": "plain_text", "text": "Reject Decision"},
                        "submit": {"type": "plain_text", "text": "Reject"},
                        "close": {"type": "plain_text", "text": "Cancel"},
                        "blocks": [
                            {
                                "type": "section",
                                "text": {"type": "mrkdwn", "text": "Please provide a reason for rejecting this decision."}
                            },
                            {
                                "type": "input",
                                "block_id": "reason_block",
                                "element": {
                                    "type": "plain_text_input",
                                    "action_id": "reason_input",
                                    "multiline": True,
                                    "placeholder": {"type": "plain_text", "text": "Why are you rejecting this decision?"}
                                },
                                "label": {"type": "plain_text", "text": "Reason"}
                            }
                        ]
                    }
                    # Open the modal
                    modal_url = "https://slack.com/api/views.open"
                    modal_payload = json.dumps({"trigger_id": trigger_id, "view": modal}).encode()
                    modal_req = urllib.request.Request(modal_url, data=modal_payload, headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    })
                    try:
                        urllib.request.urlopen(modal_req, timeout=5)
                    except Exception as e:
                        print(f"[SLACK] Error opening reject modal: {e}")
                    return {}

    return {}


def handle_approval_action(conn, decision_id: str, slack_user_id: str, user_name: str,
                           status: str, comment: str, payload: dict) -> dict:
    """Handle approval/rejection of a decision from Slack.

    This mirrors the logic in /api/v1/decisions/[id].py POST handler.
    """
    from sqlalchemy import text

    # Get the user's database ID
    result = conn.execute(text("""
        SELECT id FROM users WHERE slack_user_id = :slack_id AND deleted_at IS NULL
    """), {"slack_id": slack_user_id})
    user_row = result.fetchone()

    if not user_row:
        return {
            "response_type": "ephemeral",
            "replace_original": False,
            "text": "❌ You need to be registered in Imputable to approve decisions. Please contact your admin."
        }

    db_user_id = str(user_row[0])

    # Get decision info including Slack channel for notifications
    result = conn.execute(text("""
        SELECT d.id, d.status, d.current_version_id, d.decision_number, dv.title, d.organization_id,
               d.slack_channel_id, o.slack_access_token
        FROM decisions d
        JOIN decision_versions dv ON d.current_version_id = dv.id
        JOIN organizations o ON d.organization_id = o.id
        WHERE d.id = :did AND d.deleted_at IS NULL
    """), {"did": decision_id})
    dec_row = result.fetchone()

    if not dec_row:
        return {
            "response_type": "ephemeral",
            "replace_original": False,
            "text": "❌ Decision not found."
        }

    decision_status = dec_row[1]
    current_version_id = str(dec_row[2])
    decision_number = dec_row[3]
    decision_title = dec_row[4]
    org_id = str(dec_row[5])
    slack_channel_id = dec_row[6]
    encrypted_token = dec_row[7]

    # Validate decision status - only pending_review decisions can be approved
    if decision_status == "approved":
        return {
            "response_type": "ephemeral",
            "replace_original": False,
            "text": "❌ This decision has already been approved and cannot be modified."
        }
    if decision_status == "draft":
        return {
            "response_type": "ephemeral",
            "replace_original": False,
            "text": "❌ This decision is still in draft status. It must be set to 'Pending Review' before it can be approved."
        }
    if decision_status in ("deprecated", "superseded"):
        return {
            "response_type": "ephemeral",
            "replace_original": False,
            "text": f"❌ This decision has been {decision_status} and cannot be approved."
        }

    # Check if user is a required reviewer
    result = conn.execute(text("""
        SELECT id, required_role FROM required_reviewers
        WHERE decision_version_id = :version_id AND user_id = :user_id
    """), {"version_id": current_version_id, "user_id": db_user_id})
    reviewer_row = result.fetchone()

    if not reviewer_row:
        return {
            "response_type": "ephemeral",
            "replace_original": False,
            "text": "❌ You are not a required reviewer for this decision."
        }

    # Parse DM info from required_role field (we store it there)
    dm_info = None
    if reviewer_row[1]:
        try:
            dm_info = json.loads(reviewer_row[1])
        except:
            pass

    # Check for existing approval and upsert
    result = conn.execute(text("""
        SELECT id FROM approvals
        WHERE decision_version_id = :version_id AND user_id = :user_id
    """), {"version_id": current_version_id, "user_id": db_user_id})
    existing = result.fetchone()

    if existing:
        conn.execute(text("""
            UPDATE approvals SET status = :status, comment = :comment, created_at = NOW()
            WHERE id = :id
        """), {"status": status, "comment": comment or "", "id": existing[0]})
    else:
        conn.execute(text("""
            INSERT INTO approvals (id, decision_version_id, user_id, status, comment, created_at)
            VALUES (:id, :version_id, :user_id, :status, :comment, NOW())
        """), {"id": str(uuid4()), "version_id": current_version_id, "user_id": db_user_id,
               "status": status, "comment": comment or ""})

    # Get counts
    result = conn.execute(text("""
        SELECT
            (SELECT COUNT(*) FROM required_reviewers WHERE decision_version_id = :version_id) as required_count,
            (SELECT COUNT(*) FROM approvals WHERE decision_version_id = :version_id AND status = 'approved') as approved_count
    """), {"version_id": current_version_id})
    counts = result.fetchone()
    required_count = counts[0]
    approved_count = counts[1]

    # Auto-approve decision if all reviewers approved
    decision_became_approved = False
    if required_count > 0 and approved_count >= required_count:
        conn.execute(text("UPDATE decisions SET status = 'approved' WHERE id = :did"), {"did": decision_id})
        decision_became_approved = True

    conn.commit()

    # Send channel notification if we have a channel
    if slack_channel_id and encrypted_token:
        try:
            token = decrypt_token(encrypted_token)
            if token:
                send_approval_channel_notification(
                    token=token,
                    channel_id=slack_channel_id,
                    decision_id=decision_id,
                    decision_number=decision_number,
                    title=decision_title,
                    approver_name=user_name,
                    status=status,
                    comment=comment,
                    approved_count=approved_count,
                    required_count=required_count,
                    decision_became_approved=decision_became_approved
                )
        except Exception as e:
            print(f"[SLACK] Error sending channel notification: {e}")

    # Build response message
    decision_url = f"https://imputable.vercel.app/decisions/{decision_id}"

    if status == "approved":
        if decision_became_approved:
            emoji = "🎉"
            status_text = "Decision Approved!"
            message = f"You approved *DECISION-{decision_number}: {decision_title}*\n\nAll required approvals received - the decision is now officially approved!"
        else:
            emoji = "✅"
            status_text = "Vote Recorded"
            message = f"You approved *DECISION-{decision_number}: {decision_title}*\n\nProgress: {approved_count}/{required_count} approved"
    else:
        emoji = "❌"
        status_text = "Vote Recorded"
        reason_text = f"\n\n_Reason: {comment}_" if comment else ""
        message = f"You rejected *DECISION-{decision_number}: {decision_title}*{reason_text}\n\nProgress: {approved_count}/{required_count} approved"

    # Update the original message to show the action was taken
    return {
        "response_type": "in_channel",
        "replace_original": True,
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": f"{emoji} {status_text}", "emoji": True}},
            {"type": "section", "text": {"type": "mrkdwn", "text": message}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "View Decision"}, "url": decision_url, "action_id": "view_decision"}
            ]}
        ]
    }


def send_approval_channel_notification(token: str, channel_id: str, decision_id: str,
                                        decision_number: int, title: str, approver_name: str,
                                        status: str, comment: str, approved_count: int,
                                        required_count: int, decision_became_approved: bool) -> bool:
    """Send approval notification to the Slack channel where decision was created."""
    decision_url = f"https://imputable.vercel.app/decisions/{decision_id}"

    if status == "approved":
        emoji = "✅"
        action_text = "approved"
        color = "10b981"
    else:
        emoji = "❌"
        action_text = "rejected"
        color = "ef4444"

    if decision_became_approved:
        header_text = "🎉 Decision Approved"
        progress_text = f"All {required_count} required reviewers have approved!"
    else:
        header_text = f"{emoji} Vote Submitted"
        progress_text = f"Progress: {approved_count}/{required_count} approved"

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": header_text, "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*<{decision_url}|DECISION-{decision_number}: {title}>*"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{approver_name}* {action_text} this decision."}},
    ]
    if comment:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"_\"{comment}\"_"}})
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": progress_text}]})
    blocks.append({"type": "actions", "elements": [
        {"type": "button", "text": {"type": "plain_text", "text": "View Decision", "emoji": True},
         "url": decision_url, "style": "primary", "action_id": "view_decision"}
    ]})

    payload = json.dumps({
        "channel": channel_id,
        "text": f"{approver_name} {action_text} DECISION-{decision_number}",
        "attachments": [{"color": color, "blocks": blocks}]
    }).encode()

    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    )

    try:
        response = urllib.request.urlopen(req, timeout=10)
        data = json.loads(response.read().decode())
        if not data.get("ok"):
            print(f"[SLACK] Error sending channel notification: {data.get('error')}")
            return False
        print(f"[SLACK] Sent channel notification for DECISION-{decision_number}")
        return True
    except Exception as e:
        print(f"[SLACK] Error sending channel notification: {e}")
        return False


# =============================================================================
# TEAMS HANDLERS
# =============================================================================

def handle_teams_activity(activity: dict, conn) -> dict:
    """Handle Teams Bot Framework activity."""
    from sqlalchemy import text

    activity_type = activity.get("type")
    conversation = activity.get("conversation", {})
    tenant_id = conversation.get("tenantId") or activity.get("channelData", {}).get("tenant", {}).get("id")

    # Get org by tenant
    result = conn.execute(text("SELECT id, name FROM organizations WHERE teams_tenant_id = :tenant_id"), {"tenant_id": tenant_id})
    org = result.fetchone()

    if not org:
        return {"type": "message", "text": "This Teams workspace is not connected to Imputable."}

    org_id, org_name = str(org[0]), org[1]
    frontend_url = os.environ.get("FRONTEND_URL", "https://imputable.vercel.app")

    if activity_type == "message":
        text_content = activity.get("text", "").strip()

        # Remove bot mention
        for entity in activity.get("entities", []):
            if entity.get("type") == "mention":
                text_content = text_content.replace(entity.get("text", ""), "").strip()

        text_lower = text_content.lower()

        # Help
        if text_lower in ("help", "?", ""):
            return {
                "type": "message",
                "text": f"**Imputable Bot**\n\nCommands:\n- `search <query>` - Search decisions\n- `poll <question>` - Start consensus poll\n- `help` - Show this message\n\n[Open Imputable]({frontend_url})"
            }

        # Search
        if text_lower.startswith("search "):
            query = text_content[7:].strip()
            result = conn.execute(text("""
                SELECT d.id, d.decision_number, dv.title, d.status
                FROM decisions d
                JOIN decision_versions dv ON d.current_version_id = dv.id
                WHERE d.organization_id = :org_id AND d.deleted_at IS NULL
                  AND (LOWER(dv.title) LIKE :query OR LOWER(dv.content::text) LIKE :query)
                ORDER BY d.created_at DESC LIMIT 5
            """), {"org_id": org_id, "query": f"%{query.lower()}%"})
            decisions = result.fetchall()

            if not decisions:
                return {"type": "message", "text": f"No decisions found for: {query}"}

            lines = [f"**Search results for:** {query}\n"]
            for d in decisions:
                lines.append(f"- [DECISION-{d[1]}: {d[2]}]({frontend_url}/decisions/{d[0]})")

            return {"type": "message", "text": "\n".join(lines)}

        # Poll
        if text_lower.startswith("poll "):
            question = text_content[5:].strip()
            return {"type": "message", "text": f"Poll feature coming soon: {question}"}

        return {"type": "message", "text": f"Unknown command. Type `help` for available commands."}

    return {}


# =============================================================================
# MAIN HANDLER
# =============================================================================

class handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Slack-Signature, X-Slack-Request-Timestamp")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode() if isinstance(body, (dict, list)) else body.encode() if isinstance(body, str) else body)
        self.wfile.flush()

    def do_OPTIONS(self):
        self._send(204, "")

    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            platform = query.get("platform", [""])[0]
            req_type = query.get("type", [""])[0]

            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)

            # Handle async save request (fired from view_submission, no signature needed)
            if platform == "slack" and req_type == "async_save":
                print(f"[SLACK ASYNC SAVE] Received async save request")
                try:
                    data = json.loads(body.decode()) if body else {}
                    if data.get("action") != "save_decision":
                        print(f"[SLACK ASYNC SAVE] Invalid action: {data.get('action')}")
                        self._send(200, {})
                        return

                    team_id = data.get("team_id")
                    payload = data.get("payload", {})

                    token = os.environ.get("SLACK_BOT_TOKEN", "")
                    values = payload.get("view", {}).get("state", {}).get("values", {})
                    metadata = {}
                    try:
                        metadata = json.loads(payload.get("view", {}).get("private_metadata", "{}"))
                    except:
                        pass

                    user = payload.get("user", {})
                    user_id = user.get("id", "")
                    user_name = user.get("username", "") or user.get("name", "")

                    # Extract form values
                    title = values.get("title_block", {}).get("title_input", {}).get("value", "").strip()
                    if not title:
                        print(f"[SLACK ASYNC SAVE] No title provided")
                        self._send(200, {})
                        return

                    context = values.get("context_block", {}).get("context_input", {}).get("value", "") or ""
                    impact = values.get("impact_block", {}).get("impact_select", {}).get("selected_option", {}).get("value", "medium")
                    choice = values.get("choice_block", {}).get("choice_input", {}).get("value", "") or context or title
                    rationale = values.get("rationale_block", {}).get("rationale_input", {}).get("value", "") or ""
                    alternatives_text = values.get("alternatives_block", {}).get("alternatives_input", {}).get("value", "") or ""
                    required_approver = values.get("approver_block", {}).get("approver_input", {}).get("value", "").strip() or None

                    # Parse alternatives
                    alternatives = []
                    if alternatives_text:
                        for line in alternatives_text.strip().split("\n"):
                            line = line.strip()
                            if line.startswith("- "):
                                line = line[2:]
                            if ": " in line:
                                name, reason = line.split(": ", 1)
                                alternatives.append({"name": name.strip(), "rejected_reason": reason.strip()})
                            elif line:
                                alternatives.append({"name": line, "rejected_reason": ""})

                    ai_generated = metadata.get("ai_generated", False)
                    confidence_score = metadata.get("confidence_score", 0.0)
                    suggested_status = metadata.get("suggested_status", "draft")
                    has_conflict = metadata.get("has_conflict", False)

                    # Save to database
                    engine = get_db_connection()
                    if engine:
                        with engine.connect() as conn:
                            from sqlalchemy import text

                            # Single query to get org_id, user_id, and next decision number
                            result = conn.execute(text("""
                                SELECT
                                    o.id as org_id,
                                    u.id as user_id,
                                    COALESCE(MAX(d.decision_number), 0) + 1 as next_num
                                FROM organizations o
                                LEFT JOIN users u ON u.slack_user_id = :slack_user_id
                                LEFT JOIN decisions d ON d.organization_id = o.id
                                WHERE o.slack_team_id = :team_id
                                GROUP BY o.id, u.id
                            """), {"team_id": team_id, "slack_user_id": user_id})
                            row = result.fetchone()

                            if not row or not row[0]:
                                print(f"[SLACK ASYNC SAVE] Org not found for team_id: {team_id}")
                                self._send(200, {})
                                return

                            org_id = str(row[0])
                            next_num = row[2]

                            # Verify user is an active member (don't auto-create)
                            db_user_id, member_status, error_msg = get_active_member_user_id(conn, org_id, user_id)
                            if not db_user_id:
                                print(f"[SLACK ASYNC SAVE] User not active member: {error_msg}")
                                self._send(200, {})
                                return

                            decision_id = str(uuid4())
                            version_id = str(uuid4())

                            # Determine status based on context:
                            # - If conflict detected, force DRAFT
                            # - If required approver specified, use PENDING_REVIEW
                            # - Otherwise, use AI suggestion if high confidence
                            decision_status = "draft"
                            if has_conflict:
                                decision_status = "draft"
                            elif required_approver:
                                decision_status = "pending_review"
                            elif ai_generated and confidence_score >= 0.8 and suggested_status in ("draft", "pending_review", "approved"):
                                decision_status = suggested_status

                            content = json.dumps({"context": context, "choice": choice, "rationale": rationale, "alternatives": alternatives})
                            tags = ["slack-logged"]
                            if ai_generated:
                                tags.append("ai-generated")

                            custom_fields = {
                                "ai_generated": ai_generated,
                                "ai_confidence_score": confidence_score,
                                "has_conflict": has_conflict,
                                "required_approver": required_approver,
                                "verified_by_user": True,
                                "verified_by_slack_user_id": user_id
                            }

                            check_ts = metadata.get("thread_ts") or metadata.get("message_ts")

                            # Insert decision
                            conn.execute(text("""
                                INSERT INTO decisions (id, organization_id, decision_number, status, created_by, source, slack_channel_id, slack_message_ts, slack_thread_ts, is_temporary, created_at, updated_at)
                                VALUES (:id, :org_id, :num, :status, :user_id, 'slack', :channel_id, :msg_ts, :thread_ts, false, NOW(), NOW())
                            """), {
                                "id": decision_id, "org_id": org_id, "num": next_num, "status": decision_status, "user_id": db_user_id,
                                "channel_id": metadata.get("channel_id"), "msg_ts": metadata.get("message_ts"), "thread_ts": metadata.get("thread_ts")
                            })

                            conn.execute(text("""
                                INSERT INTO decision_versions (id, decision_id, version_number, title, impact_level, content, tags, created_by, created_at, custom_fields)
                                VALUES (:id, :did, 1, :title, :impact, :content, :tags, :user_id, NOW(), :custom_fields)
                            """), {
                                "id": version_id, "did": decision_id, "title": title[:255], "impact": impact,
                                "content": content, "tags": tags, "user_id": db_user_id,
                                "custom_fields": json.dumps(custom_fields) if custom_fields else None
                            })

                            conn.execute(text("UPDATE decisions SET current_version_id = :vid WHERE id = :did"), {"vid": version_id, "did": decision_id})

                            if check_ts and metadata.get("channel_id"):
                                conn.execute(text("""
                                    INSERT INTO logged_messages (id, source, message_id, channel_id, decision_id, created_at)
                                    VALUES (:id, 'slack', :msg_id, :channel_id, :did, NOW())
                                    ON CONFLICT (source, message_id, channel_id) DO NOTHING
                                """), {"id": str(uuid4()), "msg_id": check_ts, "channel_id": metadata.get("channel_id"), "did": decision_id})

                            # Handle required approver - create RequiredReviewer and send DM
                            approver_slack_id = None
                            approver_db_user_id = None
                            if required_approver and token:
                                print(f"[SLACK ASYNC SAVE] Looking up required approver: {required_approver}")
                                # Look up the approver in Slack
                                approver_info = lookup_slack_user_by_name(token, required_approver)
                                if approver_info and approver_info.get("id"):
                                    approver_slack_id = approver_info["id"]
                                    print(f"[SLACK ASYNC SAVE] Found approver Slack ID: {approver_slack_id}")

                                    # Resolve or create the user in our database
                                    approver_db_user_id = resolve_or_create_user_from_slack(
                                        conn, org_id, approver_info, db_user_id
                                    )
                                    print(f"[SLACK ASYNC SAVE] Approver DB user ID: {approver_db_user_id}")

                                    # Create RequiredReviewer entry
                                    conn.execute(text("""
                                        INSERT INTO required_reviewers (id, decision_version_id, user_id, added_by, added_at)
                                        VALUES (:id, :version_id, :user_id, :added_by, NOW())
                                        ON CONFLICT (decision_version_id, user_id) DO NOTHING
                                    """), {
                                        "id": str(uuid4()),
                                        "version_id": version_id,
                                        "user_id": approver_db_user_id,
                                        "added_by": db_user_id
                                    })
                                    print(f"[SLACK ASYNC SAVE] Created RequiredReviewer for {required_approver}")
                                else:
                                    print(f"[SLACK ASYNC SAVE] Could not find Slack user for: {required_approver}")

                            conn.commit()
                            print(f"[SLACK ASYNC SAVE] Decision saved to DB: DECISION-{next_num}")

                            # Send DM to approver AFTER commit (so decision exists)
                            if approver_slack_id and token:
                                try:
                                    requester_display = user_name or f"<@{user_id}>"
                                    dm_result = send_approval_dm(
                                        token=token,
                                        approver_slack_id=approver_slack_id,
                                        decision_id=decision_id,
                                        decision_number=next_num,
                                        title=title,
                                        requester_name=requester_display,
                                        context=context[:500] if context else None
                                    )

                                    # Store DM info in required_reviewers for later updates
                                    if dm_result.get("success"):
                                        conn.execute(text("""
                                            UPDATE required_reviewers
                                            SET required_role = :dm_info
                                            WHERE decision_version_id = :version_id AND user_id = :user_id
                                        """), {
                                            "dm_info": json.dumps({
                                                "dm_channel_id": dm_result.get("channel_id"),
                                                "dm_message_ts": dm_result.get("message_ts"),
                                                "approver_slack_id": approver_slack_id
                                            }),
                                            "version_id": version_id,
                                            "user_id": approver_db_user_id
                                        })
                                        conn.commit()
                                        print(f"[SLACK ASYNC SAVE] Stored DM info for approver")
                                except Exception as dm_err:
                                    print(f"[SLACK ASYNC SAVE] Error sending approval DM: {dm_err}")

                except Exception as e:
                    print(f"[SLACK ASYNC SAVE] Error: {e}")
                    import traceback
                    traceback.print_exc()

                self._send(200, {"ok": True})
                return

            # Handle async poll creation (fired from command fast path)
            if platform == "slack" and req_type == "async_poll":
                print(f"[SLACK ASYNC POLL] Received async poll request")
                try:
                    data = json.loads(body.decode()) if body else {}
                    team_id = data.get("team_id")
                    channel_id = data.get("channel_id")
                    user_id = data.get("user_id")
                    user_name = data.get("user_name")
                    question = data.get("question", "")
                    response_url = data.get("response_url")

                    if not question:
                        self._send(200, {})
                        return

                    token = os.environ.get("SLACK_BOT_TOKEN", "")

                    engine = get_db_connection()
                    if engine:
                        with engine.connect() as conn:
                            from sqlalchemy import text

                            # Get org
                            result = conn.execute(text("SELECT id, slack_access_token FROM organizations WHERE slack_team_id = :team_id"), {"team_id": team_id})
                            org = result.fetchone()
                            if not org:
                                self._send(200, {})
                                return

                            org_id = str(org[0])
                            if not token and org[1]:
                                token = decrypt_token(org[1])

                            # Verify user is an active member
                            db_user_id, member_status, error_msg = get_active_member_user_id(conn, org_id, user_id)
                            if not db_user_id:
                                # Send error via response_url
                                if response_url:
                                    error_payload = json.dumps({
                                        "response_type": "ephemeral",
                                        "text": f":warning: {error_msg}"
                                    }).encode()
                                    try:
                                        req = urllib.request.Request(response_url, data=error_payload, headers={"Content-Type": "application/json"})
                                        urllib.request.urlopen(req, timeout=5)
                                    except Exception:
                                        pass
                                self._send(200, {})
                                return

                            # Get channel member count for dynamic threshold
                            channel_member_count = 0
                            if token:
                                try:
                                    members_req = urllib.request.Request(
                                        f"https://slack.com/api/conversations.members?channel={channel_id}&limit=100",
                                        headers={"Authorization": f"Bearer {token}"}
                                    )
                                    members_resp = urllib.request.urlopen(members_req, timeout=5)
                                    members_data = json.loads(members_resp.read().decode())
                                    if members_data.get("ok"):
                                        channel_member_count = len(members_data.get("members", []))
                                        print(f"[SLACK ASYNC POLL] Channel has {channel_member_count} members")
                                except Exception as e:
                                    print(f"[SLACK ASYNC POLL] Failed to get channel members: {e}")

                            # Get next decision number
                            result = conn.execute(text("SELECT COALESCE(MAX(decision_number), 0) + 1 FROM decisions WHERE organization_id = :org_id"), {"org_id": org_id})
                            next_num = result.fetchone()[0]

                            decision_id = str(uuid4())
                            version_id = str(uuid4())

                            # Create decision
                            conn.execute(text("""
                                INSERT INTO decisions (id, organization_id, decision_number, status, created_by, source, slack_channel_id, is_temporary, created_at, updated_at)
                                VALUES (:id, :org_id, :num, 'pending_review', :user_id, 'slack', :channel_id, false, NOW(), NOW())
                            """), {"id": decision_id, "org_id": org_id, "num": next_num, "user_id": db_user_id, "channel_id": channel_id})

                            content = json.dumps({"context": "This decision was proposed via Slack poll for team consensus.", "choice": f"Team is voting on: {question}", "rationale": None, "alternatives": []})
                            tags = '{"slack-logged", "poll"}'
                            custom_fields = json.dumps({"channel_member_count": channel_member_count, "poll_creator_slack_id": user_id})
                            conn.execute(text("""
                                INSERT INTO decision_versions (id, decision_id, version_number, title, impact_level, content, tags, created_by, created_at, custom_fields)
                                VALUES (:id, :did, 1, :title, 'medium', :content, :tags, :user_id, NOW(), :custom_fields)
                            """), {"id": version_id, "did": decision_id, "title": question[:255], "content": content, "tags": tags, "user_id": db_user_id, "custom_fields": custom_fields})

                            conn.execute(text("UPDATE decisions SET current_version_id = :vid WHERE id = :did"), {"vid": version_id, "did": decision_id})
                            conn.commit()

                            # Build poll blocks
                            votes = {"agree": [], "concern": [], "block": []}
                            blocks = SlackBlocks.consensus_poll(decision_id, next_num, question[:255], votes, "pending_review", channel_member_count, user_id)

                            # Replace loading message with poll via response_url
                            if response_url:
                                poll_payload = json.dumps({
                                    "response_type": "in_channel",
                                    "replace_original": True,
                                    "text": f"Poll: {question[:100]}",
                                    "blocks": blocks
                                }).encode()
                                req = urllib.request.Request(
                                    response_url,
                                    data=poll_payload,
                                    headers={"Content-Type": "application/json"}
                                )
                                try:
                                    urllib.request.urlopen(req, timeout=10)
                                    print(f"[SLACK ASYNC POLL] Posted poll via response_url")
                                except Exception as e:
                                    print(f"[SLACK ASYNC POLL] Failed to post poll: {e}")

                except Exception as e:
                    print(f"[SLACK ASYNC POLL] Error: {e}")
                    import traceback
                    traceback.print_exc()

                self._send(200, {"ok": True})
                return

            # Handle async search (fired from command fast path)
            if platform == "slack" and req_type == "async_search":
                print(f"[SLACK ASYNC SEARCH] Received async search request")
                try:
                    data = json.loads(body.decode()) if body else {}
                    team_id = data.get("team_id")
                    query = data.get("query", "")
                    response_url = data.get("response_url")

                    if not query or not response_url:
                        self._send(200, {})
                        return

                    engine = get_db_connection()
                    if engine:
                        with engine.connect() as conn:
                            from sqlalchemy import text

                            # Get org
                            result = conn.execute(text("SELECT id FROM organizations WHERE slack_team_id = :team_id"), {"team_id": team_id})
                            org = result.fetchone()
                            if not org:
                                # Send error via response_url
                                error_payload = json.dumps({
                                    "response_type": "ephemeral",
                                    "replace_original": True,
                                    "text": ":warning: Organization not found."
                                }).encode()
                                req = urllib.request.Request(response_url, data=error_payload, headers={"Content-Type": "application/json"})
                                try:
                                    urllib.request.urlopen(req, timeout=5)
                                except:
                                    pass
                                self._send(200, {})
                                return

                            org_id = str(org[0])

                            # Fetch decisions for semantic search
                            result = conn.execute(text("""
                                SELECT d.id, d.decision_number, dv.title, d.status, dv.content, d.created_at
                                FROM decisions d
                                JOIN decision_versions dv ON d.current_version_id = dv.id
                                WHERE d.organization_id = :org_id AND d.deleted_at IS NULL
                                ORDER BY d.created_at DESC LIMIT 50
                            """), {"org_id": org_id})
                            all_decisions = result.fetchall()

                            if not all_decisions:
                                no_results_payload = json.dumps({
                                    "response_type": "ephemeral",
                                    "replace_original": True,
                                    "text": ":mag: No decisions found in your organization yet."
                                }).encode()
                                req = urllib.request.Request(response_url, data=no_results_payload, headers={"Content-Type": "application/json"})
                                try:
                                    urllib.request.urlopen(req, timeout=5)
                                except:
                                    pass
                                self._send(200, {})
                                return

                            # Convert to list of dicts for semantic search
                            decisions_for_search = []
                            decisions_by_id = {}
                            for row in all_decisions:
                                d = {
                                    "id": str(row[0]),
                                    "decision_number": row[1],
                                    "title": row[2],
                                    "status": row[3],
                                    "content": row[4],
                                    "created_at": str(row[5]) if row[5] else ""
                                }
                                decisions_for_search.append(d)
                                decisions_by_id[str(row[0])] = d

                            # Use AI to find relevant decisions
                            search_result = semantic_search_decisions(query, decisions_for_search)

                            matched_ids = search_result.get("matches", [])
                            explanation = search_result.get("explanation", "")
                            best_match = search_result.get("best_match_summary", "")

                            if not matched_ids:
                                blocks = SlackBlocks.semantic_search_results(query, [], explanation)
                            else:
                                # Get matched decisions in order
                                matched_decisions = []
                                for mid in matched_ids:
                                    if mid in decisions_by_id:
                                        d = decisions_by_id[mid]
                                        matched_decisions.append((d["id"], d["decision_number"], d["title"], d["status"]))
                                blocks = SlackBlocks.semantic_search_results(query, matched_decisions, explanation, best_match)

                            # Send results via response_url, replacing the "Searching..." message
                            results_payload = json.dumps({
                                "response_type": "ephemeral",
                                "replace_original": True,
                                "blocks": blocks
                            }).encode()
                            req = urllib.request.Request(response_url, data=results_payload, headers={"Content-Type": "application/json"})
                            try:
                                urllib.request.urlopen(req, timeout=10)
                                print(f"[SLACK ASYNC SEARCH] Sent results for query: {query}")
                            except Exception as e:
                                print(f"[SLACK ASYNC SEARCH] Failed to send results: {e}")

                except Exception as e:
                    print(f"[SLACK ASYNC SEARCH] Error: {e}")
                    import traceback
                    traceback.print_exc()

                self._send(200, {"ok": True})
                return

            # ASYNC POLL VOTE handler
            if platform == "slack" and req_type == "async_poll_vote":
                from sqlalchemy import text
                print(f"[SLACK ASYNC VOTE] Received async vote request")
                try:
                    data = json.loads(body.decode())
                    team_id = data.get("team_id", "")
                    decision_id = data.get("decision_id", "")
                    vote_type = data.get("vote_type", "")
                    user_id = data.get("user_id", "")
                    user_name = data.get("user_name", "")
                    response_url = data.get("response_url", "")

                    engine = get_db_connection()
                    if engine:
                        with engine.connect() as conn:
                            # Upsert vote
                            result = conn.execute(text("""
                                SELECT id FROM poll_votes
                                WHERE decision_id = :did AND external_user_id = :uid AND source = 'slack'
                            """), {"did": decision_id, "uid": user_id})
                            existing = result.fetchone()

                            if existing:
                                conn.execute(text("""
                                    UPDATE poll_votes SET vote_type = :vote, external_user_name = :name, updated_at = NOW()
                                    WHERE id = :id
                                """), {"vote": vote_type, "name": user_name, "id": existing[0]})
                            else:
                                conn.execute(text("""
                                    INSERT INTO poll_votes (id, decision_id, external_user_id, external_user_name, vote_type, source, created_at, updated_at)
                                    VALUES (:id, :did, :uid, :name, :vote, 'slack', NOW(), NOW())
                                """), {"id": str(uuid4()), "did": decision_id, "uid": user_id, "name": user_name, "vote": vote_type})

                            conn.commit()

                            # Get updated votes and decision info
                            result = conn.execute(text("""
                                SELECT d.decision_number, dv.title, d.status, dv.custom_fields, d.created_at
                                FROM decisions d
                                JOIN decision_versions dv ON d.current_version_id = dv.id
                                WHERE d.id = :did
                            """), {"did": decision_id})
                            dec = result.fetchone()

                            if dec and response_url:
                                result = conn.execute(text("SELECT vote_type, external_user_name FROM poll_votes WHERE decision_id = :did"), {"did": decision_id})
                                votes = {"agree": [], "concern": [], "block": []}
                                for row in result.fetchall():
                                    vt, name = row[0], row[1] or "Someone"
                                    if vt in votes:
                                        votes[vt].append(name)

                                # Get channel_member_count and creator from custom_fields
                                channel_member_count = 0
                                creator_slack_id = ""
                                if dec[3]:
                                    cf = dec[3] if isinstance(dec[3], dict) else json.loads(dec[3]) if dec[3] else {}
                                    channel_member_count = cf.get("channel_member_count", 0)
                                    creator_slack_id = cf.get("poll_creator_slack_id", "")

                                # Check if consensus just reached on old poll (1+ day old)
                                import math
                                from datetime import datetime, timezone
                                threshold = max(2, min(10, math.ceil(channel_member_count * 0.6))) if channel_member_count > 0 else 3
                                consensus_reached = len(votes["agree"]) >= threshold and len(votes["block"]) == 0

                                if consensus_reached and dec[2] != "approved" and creator_slack_id:
                                    # Check if poll is 1+ day old
                                    created_at = dec[4]
                                    if created_at:
                                        now = datetime.now(timezone.utc)
                                        if hasattr(created_at, 'tzinfo') and created_at.tzinfo is None:
                                            created_at = created_at.replace(tzinfo=timezone.utc)
                                        age_hours = (now - created_at).total_seconds() / 3600

                                        if age_hours >= 24:
                                            # Send DM to creator
                                            token = os.environ.get("SLACK_BOT_TOKEN", "")
                                            if token:
                                                frontend_url = os.environ.get("FRONTEND_URL", "https://imputable.vercel.app")
                                                dm_blocks = [
                                                    {"type": "section", "text": {"type": "mrkdwn", "text": f":tada: *Consensus reached on your poll!*\n\n*{dec[1]}*\n\nThe team has reached consensus. You can now approve this decision."}},
                                                    {"type": "actions", "elements": [
                                                        {"type": "button", "text": {"type": "plain_text", "text": "View Decision"}, "url": f"{frontend_url}/decisions/{decision_id}"}
                                                    ]}
                                                ]
                                                dm_payload = json.dumps({"channel": creator_slack_id, "text": f"Consensus reached on: {dec[1]}", "blocks": dm_blocks}).encode()
                                                dm_req = urllib.request.Request("https://slack.com/api/chat.postMessage", data=dm_payload, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
                                                try:
                                                    urllib.request.urlopen(dm_req, timeout=5)
                                                    print(f"[SLACK ASYNC VOTE] Sent consensus DM to creator {creator_slack_id}")
                                                except Exception as dm_e:
                                                    print(f"[SLACK ASYNC VOTE] Failed to send DM: {dm_e}")

                                blocks = SlackBlocks.consensus_poll(decision_id, dec[0], dec[1], votes, dec[2], channel_member_count, creator_slack_id)
                                update_payload = json.dumps({
                                    "replace_original": True,
                                    "blocks": blocks
                                }).encode()

                                req = urllib.request.Request(
                                    response_url,
                                    data=update_payload,
                                    headers={"Content-Type": "application/json"}
                                )
                                try:
                                    urllib.request.urlopen(req, timeout=5)
                                    print(f"[SLACK ASYNC VOTE] Updated poll via response_url")
                                except Exception as e:
                                    print(f"[SLACK ASYNC VOTE] Failed to update: {e}")

                except Exception as e:
                    print(f"[SLACK ASYNC VOTE] Error: {e}")
                    import traceback
                    traceback.print_exc()

                self._send(200, {"ok": True})
                return

            # ASYNC POLL APPROVE handler
            if platform == "slack" and req_type == "async_poll_approve":
                from sqlalchemy import text
                print(f"[SLACK ASYNC APPROVE] Received async approve request")
                try:
                    data = json.loads(body.decode())
                    team_id = data.get("team_id", "")
                    decision_id = data.get("decision_id", "")
                    user_id = data.get("user_id", "")
                    user_name = data.get("user_name", "")
                    response_url = data.get("response_url", "")

                    engine = get_db_connection()
                    if engine:
                        with engine.connect() as conn:
                            # Update decision status to approved
                            conn.execute(text("""
                                UPDATE decisions SET status = 'approved', updated_at = NOW()
                                WHERE id = :did AND status != 'approved'
                            """), {"did": decision_id})
                            conn.commit()

                            # Get updated decision info
                            result = conn.execute(text("""
                                SELECT d.decision_number, dv.title, d.status
                                FROM decisions d
                                JOIN decision_versions dv ON d.current_version_id = dv.id
                                WHERE d.id = :did
                            """), {"did": decision_id})
                            dec = result.fetchone()

                            if dec and response_url:
                                result = conn.execute(text("SELECT vote_type, external_user_name FROM poll_votes WHERE decision_id = :did"), {"did": decision_id})
                                votes = {"agree": [], "concern": [], "block": []}
                                for row in result.fetchall():
                                    vt, name = row[0], row[1] or "Someone"
                                    if vt in votes:
                                        votes[vt].append(name)

                                blocks = SlackBlocks.consensus_poll(decision_id, dec[0], dec[1], votes, dec[2])
                                update_payload = json.dumps({
                                    "replace_original": True,
                                    "blocks": blocks
                                }).encode()

                                req = urllib.request.Request(
                                    response_url,
                                    data=update_payload,
                                    headers={"Content-Type": "application/json"}
                                )
                                try:
                                    urllib.request.urlopen(req, timeout=5)
                                    print(f"[SLACK ASYNC APPROVE] Updated poll via response_url")
                                except Exception as e:
                                    print(f"[SLACK ASYNC APPROVE] Failed to update: {e}")

                except Exception as e:
                    print(f"[SLACK ASYNC APPROVE] Error: {e}")
                    import traceback
                    traceback.print_exc()

                self._send(200, {"ok": True})
                return

            # Async handler for /decision log AI analysis
            if platform == "slack" and req_type == "async_log":
                print(f"[SLACK ASYNC LOG] Received async log request")
                try:
                    data = json.loads(body.decode())
                    view_id = data.get("view_id", "")
                    channel_id = data.get("channel_id", "")
                    hint = data.get("hint", "")
                    token = data.get("token", "")

                    if not view_id or not token:
                        print(f"[SLACK ASYNC LOG] Missing view_id or token")
                        self._send(200, {"ok": False})
                        return

                    # Fetch recent messages
                    print(f"[SLACK ASYNC LOG] Fetching messages for channel {channel_id}")
                    messages = fetch_recent_channel_messages(token, channel_id, limit=50)
                    print(f"[SLACK ASYNC LOG] Got {len(messages) if messages else 0} messages")

                    if messages:
                        messages = resolve_slack_user_names(token, messages)

                        # Get channel name
                        channel_name = ""
                        try:
                            channel_req = urllib.request.Request(
                                f"https://slack.com/api/conversations.info?channel={channel_id}",
                                headers={"Authorization": f"Bearer {token}"}
                            )
                            channel_resp = urllib.request.urlopen(channel_req, timeout=5)
                            channel_data = json.loads(channel_resp.read().decode())
                            if channel_data.get("ok"):
                                channel_name = channel_data.get("channel", {}).get("name", "")
                        except:
                            pass

                        # AI analysis
                        gemini_key = os.environ.get("GEMINI_API_KEY", "")
                        if gemini_key:
                            print(f"[SLACK ASYNC LOG] Starting AI analysis")
                            analysis = analyze_with_gemini(messages, channel_name, hint=hint if hint else None)
                            print(f"[SLACK ASYNC LOG] AI analysis done, got result: {bool(analysis)}")
                            if analysis:
                                latest_ts = messages[-1].get("timestamp", "") if messages else ""
                                modal = SlackModals.ai_prefilled_modal(analysis, channel_id, latest_ts, None)
                            else:
                                prefill_title = hint if hint else "Decision from recent conversation"
                                modal = SlackModals.log_message(prefill_title, "", channel_id, "", None)
                        else:
                            print(f"[SLACK ASYNC LOG] No GEMINI_API_KEY, using basic modal")
                            prefill_title = hint if hint else "Decision from recent conversation"
                            modal = SlackModals.log_message(prefill_title, "", channel_id, "", None)

                        # Update modal with results
                        print(f"[SLACK ASYNC LOG] Updating modal {view_id}")
                        update_data = json.dumps({"view_id": view_id, "view": modal}).encode()
                        update_req = urllib.request.Request(
                            "https://slack.com/api/views.update",
                            data=update_data,
                            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                        )
                        update_resp = urllib.request.urlopen(update_req, timeout=10)
                        update_resp_data = json.loads(update_resp.read().decode())
                        print(f"[SLACK ASYNC LOG] Modal update response: ok={update_resp_data.get('ok')}, error={update_resp_data.get('error')}")
                    else:
                        # No messages - show error modal
                        error_modal = {
                            "type": "modal",
                            "callback_id": "log_error_modal",
                            "title": {"type": "plain_text", "text": "No Messages"},
                            "close": {"type": "plain_text", "text": "Close"},
                            "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": ":warning: No recent messages found in this channel to analyze."}}]
                        }
                        update_data = json.dumps({"view_id": view_id, "view": error_modal}).encode()
                        update_req = urllib.request.Request(
                            "https://slack.com/api/views.update",
                            data=update_data,
                            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                        )
                        urllib.request.urlopen(update_req, timeout=5)

                except Exception as e:
                    print(f"[SLACK ASYNC LOG] Error: {e}")
                    import traceback
                    traceback.print_exc()
                    # Try to update modal with error
                    try:
                        if view_id and token:
                            error_modal = {
                                "type": "modal",
                                "callback_id": "log_error_modal",
                                "title": {"type": "plain_text", "text": "Error"},
                                "close": {"type": "plain_text", "text": "Close"},
                                "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": ":warning: *Failed to analyze conversation.*\n\nPlease try again or use `/decision add` to create a decision manually."}}]
                            }
                            update_data = json.dumps({"view_id": view_id, "view": error_modal}).encode()
                            update_req = urllib.request.Request(
                                "https://slack.com/api/views.update",
                                data=update_data,
                                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                            )
                            urllib.request.urlopen(update_req, timeout=5)
                    except:
                        pass

                self._send(200, {"ok": True})
                return

            # FAST PATH for slash commands - respond immediately, process async
            if platform == "slack" and req_type == "command":
                # Verify signature first
                sig = self.headers.get("X-Slack-Signature", "")
                ts = self.headers.get("X-Slack-Request-Timestamp", "")

                if os.environ.get("SLACK_SIGNING_SECRET") and not verify_slack_signature(body, ts, sig):
                    self._send(401, {"error": "Invalid signature"})
                    return

                # Parse form data
                form_data = {}
                for pair in body.decode().split("&"):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        form_data[unquote(k)] = unquote(v.replace("+", " "))

                cmd_text = form_data.get("text", "").strip().lower()

                # Poll command needs async processing
                if cmd_text.startswith("poll "):
                    question = form_data.get("text", "")[5:].strip()
                    team_id = form_data.get("team_id", "")
                    channel_id = form_data.get("channel_id", "")
                    user_id = form_data.get("user_id", "")
                    user_name = form_data.get("user_name", "")
                    response_url = form_data.get("response_url", "")

                    # Fire async request
                    webhook_base = os.environ.get("WEBHOOK_URL", "https://imputable.vercel.app")
                    poll_url = f"{webhook_base}/api/v1/integrations/webhook?platform=slack&type=async_poll"

                    poll_payload = json.dumps({
                        "team_id": team_id,
                        "channel_id": channel_id,
                        "user_id": user_id,
                        "user_name": user_name,
                        "question": question,
                        "response_url": response_url
                    }).encode()

                    req = urllib.request.Request(
                        poll_url,
                        data=poll_payload,
                        headers={"Content-Type": "application/json"}
                    )
                    try:
                        urllib.request.urlopen(req, timeout=0.1)
                    except:
                        pass  # Expected to timeout

                    # Respond with loading message - async handler will replace it
                    self._send(200, {"response_type": "in_channel", "text": ":hourglass_flowing_sand: Creating poll..."})
                    return

                # Search command needs async processing (Gemini API can be slow)
                if cmd_text.startswith("search "):
                    query = form_data.get("text", "")[7:].strip()
                    team_id = form_data.get("team_id", "")
                    response_url = form_data.get("response_url", "")

                    # Fire async request
                    webhook_base = os.environ.get("WEBHOOK_URL", "https://imputable.vercel.app")
                    search_url = f"{webhook_base}/api/v1/integrations/webhook?platform=slack&type=async_search"

                    search_payload = json.dumps({
                        "team_id": team_id,
                        "query": query,
                        "response_url": response_url
                    }).encode()

                    req = urllib.request.Request(
                        search_url,
                        data=search_payload,
                        headers={"Content-Type": "application/json"}
                    )
                    try:
                        urllib.request.urlopen(req, timeout=0.1)
                    except:
                        pass  # Expected to timeout

                    # Respond with loading message - async handler will replace it
                    self._send(200, {"response_type": "ephemeral", "text": ":mag: Searching..."})
                    return

                # Add/create/new command - open modal immediately
                if cmd_text.startswith(("add ", "create ", "new ")):
                    import time as _time
                    _start = _time.time()
                    print(f"[SLACK ADD] Starting fast path at {_start}")

                    trigger_id = form_data.get("trigger_id", "")
                    team_id = form_data.get("team_id", "")
                    prefill = form_data.get("text", "").split(" ", 1)[1] if " " in form_data.get("text", "") else ""

                    if not trigger_id:
                        self._send(200, {"response_type": "ephemeral", "text": ":warning: Unable to open form. Please try again."})
                        return

                    # Try env var first (fastest)
                    token = os.environ.get("SLACK_BOT_TOKEN", "")
                    print(f"[SLACK ADD] Token from env: {'YES' if token else 'NO'}, elapsed: {_time.time() - _start:.3f}s")

                    # Fallback to DB if needed
                    if not token:
                        engine = get_db_connection()
                        if engine:
                            with engine.connect() as conn:
                                from sqlalchemy import text
                                result = conn.execute(text("SELECT slack_access_token FROM organizations WHERE slack_team_id = :team_id"), {"team_id": team_id})
                                org = result.fetchone()
                                token = decrypt_token(org[0]) if org and org[0] else None

                    if not token:
                        self._send(200, {"response_type": "ephemeral", "text": ":warning: Workspace not connected. Please reconnect Slack in settings."})
                        return

                    modal = SlackModals.create_decision(prefill_title=prefill)
                    payload_data = json.dumps({"trigger_id": trigger_id, "view": modal}).encode()
                    req = urllib.request.Request(
                        "https://slack.com/api/views.open",
                        data=payload_data,
                        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                    )
                    print(f"[SLACK ADD] About to call views.open, elapsed: {_time.time() - _start:.3f}s")
                    try:
                        resp = urllib.request.urlopen(req, timeout=5)
                        resp_data = json.loads(resp.read().decode())
                        print(f"[SLACK ADD] views.open response: ok={resp_data.get('ok')}, error={resp_data.get('error')}, elapsed: {_time.time() - _start:.3f}s")
                        self._send(200, {"response_type": "ephemeral", "text": ""})
                    except Exception as e:
                        print(f"[SLACK ADD] Failed to open modal: {e}, elapsed: {_time.time() - _start:.3f}s")
                        self._send(200, {"response_type": "ephemeral", "text": ":warning: Failed to open form. Please try again."})
                    return

                # Log command - open loading modal immediately, then do AI analysis
                if cmd_text == "log" or cmd_text.startswith("log "):
                    import time as _time
                    _start = _time.time()
                    print(f"[SLACK LOG] Starting fast path at {_start}")

                    trigger_id = form_data.get("trigger_id", "")
                    team_id = form_data.get("team_id", "")
                    channel_id = form_data.get("channel_id", "")
                    hint = form_data.get("text", "")[4:].strip() if cmd_text.startswith("log ") else ""

                    if not trigger_id:
                        self._send(200, {"response_type": "ephemeral", "text": ":warning: Unable to open form. Please try again."})
                        return

                    # Try env var first (fastest)
                    token = os.environ.get("SLACK_BOT_TOKEN", "")
                    print(f"[SLACK LOG] Token from env: {'YES' if token else 'NO'}, elapsed: {_time.time() - _start:.3f}s")

                    # Fallback to DB if needed
                    if not token:
                        engine = get_db_connection()
                        if engine:
                            with engine.connect() as conn:
                                from sqlalchemy import text
                                result = conn.execute(text("SELECT slack_access_token FROM organizations WHERE slack_team_id = :team_id"), {"team_id": team_id})
                                org = result.fetchone()
                                token = decrypt_token(org[0]) if org and org[0] else None

                    if not token:
                        self._send(200, {"response_type": "ephemeral", "text": ":warning: Workspace not connected. Please reconnect Slack in settings."})
                        return

                    # Open loading modal IMMEDIATELY
                    loading_modal = {
                        "type": "modal",
                        "callback_id": "ai_loading_modal",
                        "title": {"type": "plain_text", "text": "Analyzing..."},
                        "close": {"type": "plain_text", "text": "Cancel"},
                        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": ":sparkles: *AI is analyzing the recent conversation...*\n\nThis may take a few seconds."}}]
                    }

                    payload_data = json.dumps({"trigger_id": trigger_id, "view": loading_modal}).encode()
                    req = urllib.request.Request(
                        "https://slack.com/api/views.open",
                        data=payload_data,
                        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                    )
                    print(f"[SLACK LOG] About to call views.open, elapsed: {_time.time() - _start:.3f}s")
                    try:
                        resp = urllib.request.urlopen(req, timeout=5)
                        resp_data = json.loads(resp.read().decode())
                        print(f"[SLACK LOG] views.open response: ok={resp_data.get('ok')}, error={resp_data.get('error')}, elapsed: {_time.time() - _start:.3f}s")
                        view_id = resp_data.get("view", {}).get("id") if resp_data.get("ok") else None

                        if view_id:
                            # Fire async request for AI analysis - respond to Slack immediately
                            webhook_base = os.environ.get("WEBHOOK_URL", "https://imputable.vercel.app")
                            async_url = f"{webhook_base}/api/v1/integrations/webhook?platform=slack&type=async_log"

                            async_payload = json.dumps({
                                "view_id": view_id,
                                "channel_id": channel_id,
                                "hint": hint,
                                "token": token  # Pass token to avoid another DB lookup
                            }).encode()

                            async_req = urllib.request.Request(
                                async_url,
                                data=async_payload,
                                headers={"Content-Type": "application/json"}
                            )
                            try:
                                urllib.request.urlopen(async_req, timeout=0.1)
                            except:
                                pass  # Expected to timeout, that's fine

                        # Respond immediately to Slack
                        self._send(200, {"response_type": "ephemeral", "text": ""})
                    except Exception as e:
                        print(f"[SLACK FAST PATH] Failed to open log modal: {e}")
                        self._send(200, {"response_type": "ephemeral", "text": ":warning: Failed to open form. Please try again."})
                    return

            # For Slack interactions, handle message shortcuts BEFORE database connection
            # because trigger_id expires in 3 seconds and DB connection can be slow
            if platform == "slack" and req_type == "interactions":
                # Verify signature first
                sig = self.headers.get("X-Slack-Signature", "")
                ts = self.headers.get("X-Slack-Request-Timestamp", "")

                if os.environ.get("SLACK_SIGNING_SECRET") and not verify_slack_signature(body, ts, sig):
                    self._send(401, {"error": "Invalid signature"})
                    return

                # Parse payload
                form_str = body.decode()
                payload_str = ""
                for pair in form_str.split("&"):
                    if pair.startswith("payload="):
                        payload_str = unquote(pair[8:].replace("+", " "))
                        break

                try:
                    payload = json.loads(payload_str) if payload_str else {}
                except json.JSONDecodeError as e:
                    print(f"[SLACK FAST PATH] JSON parse error: {e}")
                    self._send(200, {"response_type": "ephemeral", "text": "Error processing request."})
                    return
                interaction_type = payload.get("type")
                callback_id = payload.get("callback_id", "")
                trigger_id = payload.get("trigger_id", "")
                team_id = payload.get("team", {}).get("id", "")

                print(f"[SLACK FAST PATH] type={interaction_type}, callback_id={callback_id}")

                # FAST PATH: For poll votes - respond immediately, process async
                if interaction_type == "block_actions":
                    actions = payload.get("actions", [])
                    if actions and actions[0].get("action_id", "").startswith("poll_vote_"):
                        action = actions[0]
                        action_id = action.get("action_id", "")
                        decision_id = action.get("value", "")
                        vote_type = action_id.replace("poll_vote_", "")
                        user_info = payload.get("user", {})
                        user_id = user_info.get("id", "")
                        user_name = user_info.get("username", "") or user_info.get("name", "")
                        response_url = payload.get("response_url", "")

                        if decision_id and vote_type in ("agree", "concern", "block"):
                            # Get current message blocks to extract votes for optimistic update
                            message = payload.get("message", {})
                            blocks = message.get("blocks", [])

                            # Parse current votes from context block (format: ":white_check_mark: user1, user2 | :warning: user3")
                            votes = {"agree": [], "concern": [], "block": []}
                            title = ""
                            channel_member_count = 0
                            creator_slack_id = ""

                            for block in blocks:
                                # Get title from header
                                if block.get("type") == "header":
                                    title = block.get("text", {}).get("text", "")

                                # Parse votes from context block
                                if block.get("type") == "context":
                                    elements = block.get("elements", [])
                                    for elem in elements:
                                        text = elem.get("text", "")
                                        if ":white_check_mark:" in text and "View" not in text:
                                            # Agree votes
                                            parts = text.replace(":white_check_mark:", "").strip()
                                            if parts:
                                                votes["agree"] = [n.strip() for n in parts.split(",") if n.strip()]
                                        if ":warning:" in text:
                                            # Concern votes - extract from section after |
                                            if "|" in text:
                                                for section in text.split("|"):
                                                    if ":warning:" in section:
                                                        parts = section.replace(":warning:", "").strip()
                                                        if parts:
                                                            votes["concern"] = [n.strip() for n in parts.split(",") if n.strip()]
                                            else:
                                                parts = text.replace(":warning:", "").strip()
                                                if parts:
                                                    votes["concern"] = [n.strip() for n in parts.split(",") if n.strip()]
                                        if ":no_entry:" in text:
                                            # Block votes
                                            if "|" in text:
                                                for section in text.split("|"):
                                                    if ":no_entry:" in section:
                                                        parts = section.replace(":no_entry:", "").strip()
                                                        if parts:
                                                            votes["block"] = [n.strip() for n in parts.split(",") if n.strip()]
                                            else:
                                                parts = text.replace(":no_entry:", "").strip()
                                                if parts:
                                                    votes["block"] = [n.strip() for n in parts.split(",") if n.strip()]

                                # Get creator from approve button value
                                if block.get("type") == "section" and block.get("accessory", {}).get("action_id") == "poll_approve_decision":
                                    val = block.get("accessory", {}).get("value", "")
                                    if "|" in val:
                                        creator_slack_id = val.split("|")[1]

                            # Remove user from all vote types first, then add to new type
                            for vt in votes:
                                votes[vt] = [n for n in votes[vt] if n != user_name]
                            votes[vote_type].append(user_name)

                            # Fire async request to process vote in DB
                            webhook_base = os.environ.get("WEBHOOK_URL", "https://imputable.vercel.app")
                            vote_url = f"{webhook_base}/api/v1/integrations/webhook?platform=slack&type=async_poll_vote"

                            vote_payload = json.dumps({
                                "team_id": team_id,
                                "decision_id": decision_id,
                                "vote_type": vote_type,
                                "user_id": user_id,
                                "user_name": user_name,
                                "response_url": response_url
                            }).encode()

                            req = urllib.request.Request(
                                vote_url,
                                data=vote_payload,
                                headers={"Content-Type": "application/json"}
                            )
                            try:
                                urllib.request.urlopen(req, timeout=0.1)
                            except:
                                pass  # Expected to timeout

                            # Respond immediately with optimistic update
                            # Use decision_number 0 since we don't need it in the card anymore
                            optimistic_blocks = SlackBlocks.consensus_poll(decision_id, 0, title, votes, "pending_review", channel_member_count, creator_slack_id)
                            self._send(200, {
                                "replace_original": True,
                                "blocks": optimistic_blocks
                            })
                            return

                    # DEAD CODE BELOW - keeping for reference but async_poll_vote handles this now
                    if False and decision_id and vote_type in ("agree", "concern", "block"):
                            try:
                                engine = get_db_connection()
                                if engine:
                                    with engine.connect() as conn:
                                        # Upsert vote
                                        result = conn.execute(text("""
                                            SELECT id FROM poll_votes
                                            WHERE decision_id = :did AND external_user_id = :uid AND source = 'slack'
                                        """), {"did": decision_id, "uid": user_id})
                                        existing = result.fetchone()

                                        if existing:
                                            conn.execute(text("""
                                                UPDATE poll_votes SET vote_type = :vote, external_user_name = :name, updated_at = NOW()
                                                WHERE id = :id
                                            """), {"vote": vote_type, "name": user_name, "id": existing[0]})
                                        else:
                                            conn.execute(text("""
                                                INSERT INTO poll_votes (id, decision_id, external_user_id, external_user_name, vote_type, source, created_at, updated_at)
                                                VALUES (:id, :did, :uid, :name, :vote, 'slack', NOW(), NOW())
                                            """), {"id": str(uuid4()), "did": decision_id, "uid": user_id, "name": user_name, "vote": vote_type})

                                        conn.commit()

                                        # Get updated votes and decision info
                                        result = conn.execute(text("""
                                            SELECT d.decision_number, dv.title, d.status, dv.custom_fields, d.created_at
                                            FROM decisions d
                                            JOIN decision_versions dv ON d.current_version_id = dv.id
                                            WHERE d.id = :did
                                        """), {"did": decision_id})
                                        dec = result.fetchone()

                                        if dec:
                                            result = conn.execute(text("SELECT vote_type, external_user_name FROM poll_votes WHERE decision_id = :did"), {"did": decision_id})
                                            votes = {"agree": [], "concern": [], "block": []}
                                            for row in result.fetchall():
                                                vt, name = row[0], row[1] or "Someone"
                                                if vt in votes:
                                                    votes[vt].append(name)

                                            # Get channel_member_count and creator from custom_fields
                                            channel_member_count = 0
                                            creator_slack_id = ""
                                            if dec[3]:
                                                cf = dec[3] if isinstance(dec[3], dict) else json.loads(dec[3]) if dec[3] else {}
                                                channel_member_count = cf.get("channel_member_count", 0)
                                                creator_slack_id = cf.get("poll_creator_slack_id", "")

                                            # Check if consensus just reached on old poll (1+ day old)
                                            import math
                                            from datetime import datetime, timezone
                                            threshold = max(2, min(10, math.ceil(channel_member_count * 0.6))) if channel_member_count > 0 else 3
                                            consensus_reached = len(votes["agree"]) >= threshold and len(votes["block"]) == 0

                                            if consensus_reached and dec[2] != "approved" and creator_slack_id:
                                                # Check if poll is 1+ day old
                                                created_at = dec[4]
                                                if created_at:
                                                    now = datetime.now(timezone.utc)
                                                    if hasattr(created_at, 'tzinfo') and created_at.tzinfo is None:
                                                        from datetime import timezone as tz
                                                        created_at = created_at.replace(tzinfo=tz.utc)
                                                    age_hours = (now - created_at).total_seconds() / 3600

                                                    if age_hours >= 24:
                                                        # Send DM to creator
                                                        token = os.environ.get("SLACK_BOT_TOKEN", "")
                                                        if token:
                                                            frontend_url = os.environ.get("FRONTEND_URL", "https://imputable.vercel.app")
                                                            dm_blocks = [
                                                                {"type": "section", "text": {"type": "mrkdwn", "text": f":tada: *Consensus reached on your poll!*\n\n*{dec[1]}*\n\nThe team has reached consensus. You can now approve this decision."}},
                                                                {"type": "actions", "elements": [
                                                                    {"type": "button", "text": {"type": "plain_text", "text": "View Decision"}, "url": f"{frontend_url}/decisions/{decision_id}"}
                                                                ]}
                                                            ]
                                                            dm_payload = json.dumps({"channel": creator_slack_id, "text": f"Consensus reached on: {dec[1]}", "blocks": dm_blocks}).encode()
                                                            dm_req = urllib.request.Request("https://slack.com/api/chat.postMessage", data=dm_payload, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
                                                            try:
                                                                urllib.request.urlopen(dm_req, timeout=5)
                                                                print(f"[SLACK POLL VOTE] Sent consensus DM to creator {creator_slack_id}")
                                                            except Exception as dm_e:
                                                                print(f"[SLACK POLL VOTE] Failed to send DM: {dm_e}")

                                            self._send(200, {
                                                "replace_original": True,
                                                "blocks": SlackBlocks.consensus_poll(decision_id, dec[0], dec[1], votes, dec[2], channel_member_count, creator_slack_id)
                                            })
                                            return
                            except Exception as e:
                                print(f"[SLACK POLL VOTE] Error: {e}")

                            self._send(200, {})
                            return

                    # Also handle poll_approve_decision inline
                    if actions and actions[0].get("action_id") == "poll_approve_decision":
                        from sqlalchemy import text
                        action = actions[0]
                        action_value = action.get("value", "")
                        user_info = payload.get("user", {})
                        clicker_id = user_info.get("id", "")

                        # Parse decision_id and creator_id from value
                        if "|" in action_value:
                            decision_id, creator_id = action_value.split("|", 1)
                        else:
                            decision_id = action_value
                            creator_id = ""

                        # Check if clicker is the creator
                        if creator_id and clicker_id != creator_id:
                            self._send(200, {
                                "response_type": "ephemeral",
                                "replace_original": False,
                                "text": ":no_entry: Only the poll creator can approve this decision."
                            })
                            return

                        if decision_id:
                            try:
                                engine = get_db_connection()
                                if engine:
                                    with engine.connect() as conn:
                                        # Update decision status to approved
                                        conn.execute(text("""
                                            UPDATE decisions SET status = 'approved', updated_at = NOW()
                                            WHERE id = :did AND status != 'approved'
                                        """), {"did": decision_id})
                                        conn.commit()

                                        # Get updated decision info
                                        result = conn.execute(text("""
                                            SELECT d.decision_number, dv.title, d.status, dv.custom_fields
                                            FROM decisions d
                                            JOIN decision_versions dv ON d.current_version_id = dv.id
                                            WHERE d.id = :did
                                        """), {"did": decision_id})
                                        dec = result.fetchone()

                                        if dec:
                                            result = conn.execute(text("SELECT vote_type, external_user_name FROM poll_votes WHERE decision_id = :did"), {"did": decision_id})
                                            votes = {"agree": [], "concern": [], "block": []}
                                            for row in result.fetchall():
                                                vt, name = row[0], row[1] or "Someone"
                                                if vt in votes:
                                                    votes[vt].append(name)

                                            # Get channel_member_count and creator from custom_fields
                                            channel_member_count = 0
                                            creator_slack_id = ""
                                            if dec[3]:
                                                cf = dec[3] if isinstance(dec[3], dict) else json.loads(dec[3]) if dec[3] else {}
                                                channel_member_count = cf.get("channel_member_count", 0)
                                                creator_slack_id = cf.get("poll_creator_slack_id", "")

                                            self._send(200, {
                                                "replace_original": True,
                                                "blocks": SlackBlocks.consensus_poll(decision_id, dec[0], dec[1], votes, dec[2], channel_member_count, creator_slack_id)
                                            })
                                            return
                            except Exception as e:
                                print(f"[SLACK POLL APPROVE] Error: {e}")

                            self._send(200, {})
                            return

                # FAST PATH: For message shortcuts, open modal immediately before DB connection
                # Note: Membership is checked when they SUBMIT the modal (in view_submission handler)
                # We don't check here because trigger_id expires in 3 seconds and DB is slow
                if interaction_type == "message_action" and callback_id == "log_message_as_decision":
                    message = payload.get("message", {})
                    channel = payload.get("channel", {})
                    message_text = message.get("text", "")
                    message_ts = message.get("ts", "")
                    thread_ts = message.get("thread_ts") or message_ts
                    channel_id = channel.get("id", "")

                    # Try to get token from env first (much faster than DB)
                    token = os.environ.get("SLACK_BOT_TOKEN", "")

                    # If not in env, fall back to database
                    if not token:
                        engine = get_db_connection()
                        if engine:
                            with engine.connect() as conn:
                                from sqlalchemy import text
                                result = conn.execute(text("SELECT slack_access_token FROM organizations WHERE slack_team_id = :team_id"), {"team_id": team_id})
                                org = result.fetchone()
                                token = decrypt_token(org[0]) if org and org[0] else None

                    if token and trigger_id:
                        # AI loading modal
                        modal = {
                            "type": "modal",
                            "callback_id": "ai_loading_modal",
                            "title": {"type": "plain_text", "text": "Analyzing..."},
                            "close": {"type": "plain_text", "text": "Cancel"},
                            "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": ":sparkles: *AI is analyzing the conversation...*\n\nThis may take a few seconds."}}]
                        }

                        # Open modal IMMEDIATELY
                        payload_data = json.dumps({"trigger_id": trigger_id, "view": modal}).encode()
                        req = urllib.request.Request(
                            "https://slack.com/api/views.open",
                            data=payload_data,
                            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                        )
                        try:
                            resp = urllib.request.urlopen(req, timeout=5)
                            resp_data = json.loads(resp.read().decode())
                            print(f"[SLACK FAST PATH] views.open: ok={resp_data.get('ok')}, error={resp_data.get('error')}")
                            view_id = resp_data.get("view", {}).get("id") if resp_data.get("ok") else None

                            # Do AI analysis and update modal
                            if view_id:
                                gemini_key = os.environ.get("GEMINI_API_KEY", "")
                                if gemini_key:
                                    try:
                                        channel_name = channel.get("name", "")
                                        # Fetch messages for context
                                        if thread_ts and thread_ts != message_ts:
                                            # Message is in a thread - fetch the whole thread
                                            messages = fetch_slack_thread(token, channel_id, thread_ts)
                                        else:
                                            # Not in a thread - fetch surrounding channel messages for context
                                            messages = fetch_channel_context(token, channel_id, message_ts, count=25)
                                            if not messages:
                                                # Fallback to just the single message
                                                messages = [{"author": message.get("user", "Unknown"), "text": message_text, "timestamp": message_ts}]
                                        messages = resolve_slack_user_names(token, messages)
                                        analysis = analyze_with_gemini(messages, channel_name)
                                        if analysis:
                                            modal = SlackModals.ai_prefilled_modal(analysis, channel_id, message_ts, thread_ts)
                                        else:
                                            prefill_title = message_text.split("\n")[0][:100] if message_text else "Decision from Slack"
                                            modal = SlackModals.log_message(prefill_title, message_text, channel_id, message_ts, thread_ts)
                                    except Exception as e:
                                        print(f"[SLACK FAST PATH] AI error: {e}")
                                        prefill_title = message_text.split("\n")[0][:100] if message_text else "Decision from Slack"
                                        modal = SlackModals.log_message(prefill_title, message_text, channel_id, message_ts, thread_ts)
                                else:
                                    prefill_title = message_text.split("\n")[0][:100] if message_text else "Decision from Slack"
                                    modal = SlackModals.log_message(prefill_title, message_text, channel_id, message_ts, thread_ts)

                                # Update modal with results
                                update_data = json.dumps({"view_id": view_id, "view": modal}).encode()
                                req = urllib.request.Request(
                                    "https://slack.com/api/views.update",
                                    data=update_data,
                                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                                )
                                try:
                                    resp = urllib.request.urlopen(req, timeout=30)
                                    resp_data = json.loads(resp.read().decode())
                                    print(f"[SLACK FAST PATH] views.update: ok={resp_data.get('ok')}, error={resp_data.get('error')}")
                                except Exception as e:
                                    print(f"[SLACK FAST PATH] views.update failed: {e}")

                        except Exception as e:
                            print(f"[SLACK FAST PATH] views.open failed: {e}")

                    self._send(200, {})
                    return

                # FAST PATH: For view submissions - respond immediately, fire async save
                view_callback_id = payload.get("view", {}).get("callback_id", "")
                print(f"[SLACK FAST PATH] view_callback_id={view_callback_id}")
                if interaction_type == "view_submission" and view_callback_id == "log_message_modal":
                    # Extract minimal data for immediate Slack message
                    token = os.environ.get("SLACK_BOT_TOKEN", "")
                    values = payload.get("view", {}).get("state", {}).get("values", {})
                    metadata = {}
                    try:
                        metadata = json.loads(payload.get("view", {}).get("private_metadata", "{}"))
                    except:
                        pass

                    title = values.get("title_block", {}).get("title_input", {}).get("value", "").strip()
                    channel_id = metadata.get("channel_id")

                    # Send immediate confirmation to Slack channel
                    if token and channel_id and title:
                        frontend_url = os.environ.get("FRONTEND_URL", "https://imputable.vercel.app")
                        msg_payload = json.dumps({
                            "channel": channel_id,
                            "text": f"Decision saved: {title}",
                            "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": f":white_check_mark: *Decision saved*\n*{title}*\n\n_Saving to <{frontend_url}/decisions|Imputable>..._"}}]
                        }).encode()
                        req = urllib.request.Request(
                            "https://slack.com/api/chat.postMessage",
                            data=msg_payload,
                            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                        )
                        try:
                            urllib.request.urlopen(req, timeout=2)
                        except:
                            pass

                    # Fire async request to save (non-blocking)
                    save_payload = json.dumps({
                        "action": "save_decision",
                        "team_id": team_id,
                        "payload": payload
                    }).encode()

                    # Get the webhook URL for async save
                    webhook_base = os.environ.get("WEBHOOK_URL", "https://imputable.vercel.app")
                    save_url = f"{webhook_base}/api/v1/integrations/webhook?platform=slack&type=async_save"

                    req = urllib.request.Request(
                        save_url,
                        data=save_payload,
                        headers={"Content-Type": "application/json"}
                    )
                    try:
                        # Fire and forget - 0.1s timeout just to send, don't wait for response
                        urllib.request.urlopen(req, timeout=0.1)
                    except:
                        pass  # Expected to timeout, that's fine

                    # Return 200 immediately to close modal
                    self._send(200, {})
                    return

            engine = get_db_connection()
            if not engine:
                self._send(500, {"error": "Database not configured"})
                return

            with engine.connect() as conn:
                # Slack command
                if platform == "slack" and req_type == "command":
                    # Verify signature
                    sig = self.headers.get("X-Slack-Signature", "")
                    ts = self.headers.get("X-Slack-Request-Timestamp", "")

                    if os.environ.get("SLACK_SIGNING_SECRET") and not verify_slack_signature(body, ts, sig):
                        self._send(401, {"error": "Invalid signature"})
                        return

                    # Parse form data
                    form_data = {}
                    for pair in body.decode().split("&"):
                        if "=" in pair:
                            k, v = pair.split("=", 1)
                            form_data[unquote(k)] = unquote(v.replace("+", " "))

                    result = handle_slack_command(form_data, conn)
                    self._send(200, result)

                # Slack interactions
                elif platform == "slack" and req_type == "interactions":
                    print(f"[SLACK INTERACTIONS] Received request, body length: {len(body)}")

                    # Verify signature
                    sig = self.headers.get("X-Slack-Signature", "")
                    ts = self.headers.get("X-Slack-Request-Timestamp", "")

                    print(f"[SLACK INTERACTIONS] Signature: {sig[:20]}... Timestamp: {ts}")

                    if os.environ.get("SLACK_SIGNING_SECRET") and not verify_slack_signature(body, ts, sig):
                        print(f"[SLACK INTERACTIONS] Signature verification FAILED")
                        self._send(401, {"error": "Invalid signature"})
                        return

                    print(f"[SLACK INTERACTIONS] Signature OK, processing...")

                    # Parse payload
                    form_str = body.decode()
                    payload_str = ""
                    for pair in form_str.split("&"):
                        if pair.startswith("payload="):
                            payload_str = unquote(pair[8:].replace("+", " "))
                            break

                    try:
                        payload = json.loads(payload_str) if payload_str else {}
                    except json.JSONDecodeError as e:
                        print(f"[SLACK INTERACTIONS] JSON parse error: {e}")
                        self._send(200, {})
                        return
                    callback_id = payload.get('callback_id', payload.get('view', {}).get('callback_id', 'N/A'))
                    print(f"[SLACK INTERACTIONS] Payload type: {payload.get('type')}, callback_id: {callback_id}")

                    try:
                        result = handle_slack_interactions(payload, conn)
                        print(f"[SLACK INTERACTIONS] Handler returned: {result}")
                        self._send(200, result)
                    except Exception as e:
                        import traceback
                        print(f"[SLACK INTERACTIONS] ERROR: {e}")
                        traceback.print_exc()
                        self._send(200, {})  # Return 200 to Slack to avoid retry

                # Teams
                elif platform == "teams":
                    try:
                        activity = json.loads(body.decode()) if body else {}
                    except json.JSONDecodeError as e:
                        print(f"[TEAMS] JSON parse error: {e}")
                        self._send(200, {})
                        return
                    result = handle_teams_activity(activity, conn)
                    self._send(200, result)

                else:
                    self._send(400, {"error": "Invalid platform or type parameter"})

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send(500, {"error": str(e)})
