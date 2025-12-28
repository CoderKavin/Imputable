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

OUTPUT FORMAT (JSON):
{
    "title": "Short descriptive title for the decision (max 100 chars)",
    "context": "Summary of the problem being solved and why a decision was needed",
    "choice": "What was actually decided - the chosen approach",
    "rationale": "Why this choice was made - the reasoning",
    "alternatives": [
        {"name": "Alternative option name", "rejected_reason": "Why it wasn't chosen"}
    ],
    "key_dissenters": ["Names of people who disagreed or raised concerns"],
    "deadlines": ["Any deadlines or timelines mentioned"],
    "suggested_status": "approved|pending_review|draft",
    "suggested_impact": "low|medium|high|critical",
    "confidence_score": 0.0-1.0,
    "analysis_notes": "Brief notes on analysis certainty"
}

STATUS GUIDELINES:
- "approved": Clear consensus, everyone agreed, decision is final
- "pending_review": Decision made but needs formal approval or has concerns
- "draft": Ambiguous, still being discussed, or no clear resolution

CONFIDENCE GUIDELINES:
- 0.9-1.0: Very clear decision with explicit consensus
- 0.7-0.9: Clear decision but some interpretation needed
- 0.5-0.7: Decision exists but context is incomplete
- 0.3-0.5: Possible decision, significant uncertainty
- 0.0-0.3: Very unclear, may not be a decision at all"""


def analyze_with_gemini(messages: list, channel_name: str = None) -> dict:
    """Analyze messages with Google Gemini API."""
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        return None

    # Format transcript
    lines = []
    if channel_name:
        lines.append(f"Channel: #{channel_name}\n")
    lines.append("=== CONVERSATION TRANSCRIPT ===\n")
    for msg in messages:
        author = msg.get("author", "Unknown")
        text = msg.get("text", "")
        lines.append(f"{author}:\n  {text}\n")
    lines.append("=== END TRANSCRIPT ===")
    transcript = "\n".join(lines)

    # Call Gemini
    url = f"{GEMINI_API_URL}?key={gemini_key}"
    payload = json.dumps({
        "contents": [{
            "parts": [
                {"text": AI_SYSTEM_PROMPT},
                {"text": f"\n\nAnalyze this conversation and extract the decision:\n\n{transcript}"}
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

        return json.loads(text.strip())
    except Exception as e:
        print(f"Gemini API error: {e}")
        return None


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

def get_db_connection():
    """Get database connection."""
    from sqlalchemy import create_engine
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        return None
    return create_engine(db_url, connect_args={"sslmode": "require"})


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
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Available Commands:*\n\n`/decisions` - Show main menu\n`/decisions add <title>` - Create a new decision\n`/decisions list` - View recent decisions\n`/decisions search <query>` - Search decisions\n`/decisions poll <question>` - Start consensus poll\n`/decisions help` - Show this help"}},
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
            frontend_url = os.environ.get("FRONTEND_URL", "https://app.imputable.io")
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"{emoji} *<{frontend_url}/decisions/{dec_id}|DEC-{dec_num}>*\n{title}"},
                "accessory": {"type": "button", "text": {"type": "plain_text", "text": "View"}, "url": f"{frontend_url}/decisions/{dec_id}"}
            })

        return blocks

    @staticmethod
    def consensus_poll(decision_id: str, decision_number: int, title: str, votes: dict):
        agree = votes.get("agree", [])
        concern = votes.get("concern", [])
        block = votes.get("block", [])
        total = len(agree) + len(concern) + len(block)

        frontend_url = os.environ.get("FRONTEND_URL", "https://app.imputable.io")

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": f"DEC-{decision_number}: {title[:50]}", "emoji": True}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Consensus Poll* - {total} vote{'s' if total != 1 else ''}"}},
            {"type": "actions", "block_id": f"poll_{decision_id}", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": f"Agree ({len(agree)})", "emoji": True}, "style": "primary", "action_id": "poll_vote_agree", "value": decision_id},
                {"type": "button", "text": {"type": "plain_text", "text": f"Concern ({len(concern)})", "emoji": True}, "action_id": "poll_vote_concern", "value": decision_id},
                {"type": "button", "text": {"type": "plain_text", "text": f"Block ({len(block)})", "emoji": True}, "style": "danger", "action_id": "poll_vote_block", "value": decision_id}
            ]}
        ]

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

        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"<{frontend_url}/decisions/{decision_id}|View full decision>"}]})

        return blocks

    @staticmethod
    def decision_created(decision_id: str, decision_number: int, title: str):
        frontend_url = os.environ.get("FRONTEND_URL", "https://app.imputable.io")
        return [
            {"type": "section", "text": {"type": "mrkdwn", "text": f":white_check_mark: *Decision logged*\n*<{frontend_url}/decisions/{decision_id}|DEC-{decision_number}>*: {title}"}}
        ]

    @staticmethod
    def duplicate_warning(decision_id: str, decision_number: int, title: str):
        frontend_url = os.environ.get("FRONTEND_URL", "https://app.imputable.io")
        return [
            {"type": "section", "text": {"type": "mrkdwn", "text": f":warning: This message was already logged as *<{frontend_url}/decisions/{decision_id}|DEC-{decision_number}>*: {title}"}}
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
        # Format alternatives
        alternatives_text = ""
        if analysis.get("alternatives"):
            alt_lines = []
            for alt in analysis.get("alternatives", [])[:5]:
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

    # Search
    if cmd_lower.startswith("search "):
        query = cmd_text[7:].strip()
        result = conn.execute(text("""
            SELECT d.id, d.decision_number, dv.title, d.status
            FROM decisions d
            JOIN decision_versions dv ON d.current_version_id = dv.id
            WHERE d.organization_id = :org_id AND d.deleted_at IS NULL
              AND (LOWER(dv.title) LIKE :query OR LOWER(dv.content::text) LIKE :query)
            ORDER BY d.created_at DESC LIMIT 5
        """), {"org_id": org_id, "query": f"%{query.lower()}%"})
        decisions = result.fetchall()
        return {"response_type": "ephemeral", "blocks": SlackBlocks.search_results(query, decisions)}

    # Poll
    if cmd_lower.startswith("poll "):
        question = cmd_text[5:].strip()

        # Check if referencing existing decision (DEC-123)
        dec_match = re.match(r"^DEC-(\d+)\s*(.*)$", question, re.IGNORECASE)

        if dec_match:
            decision_number = int(dec_match.group(1))
            result = conn.execute(text("""
                SELECT d.id, d.decision_number, dv.title
                FROM decisions d
                JOIN decision_versions dv ON d.current_version_id = dv.id
                WHERE d.organization_id = :org_id AND d.decision_number = :num
            """), {"org_id": org_id, "num": decision_number})
            dec = result.fetchone()

            if not dec:
                return {"response_type": "ephemeral", "text": f":warning: Decision DEC-{decision_number} not found."}

            decision_id, decision_number, title = str(dec[0]), dec[1], dec[2]
        else:
            # Create new decision from question
            result = conn.execute(text("SELECT COALESCE(MAX(decision_number), 0) + 1 FROM decisions WHERE organization_id = :org_id"), {"org_id": org_id})
            next_num = result.fetchone()[0]

            decision_id = str(uuid4())
            version_id = str(uuid4())

            # Get or create user
            result = conn.execute(text("SELECT id FROM users WHERE slack_user_id = :slack_id"), {"slack_id": user_id})
            user_row = result.fetchone()
            if user_row:
                db_user_id = user_row[0]
            else:
                db_user_id = str(uuid4())
                conn.execute(text("""
                    INSERT INTO users (id, email, name, slack_user_id, created_at, updated_at)
                    VALUES (:id, :email, :name, :slack_id, NOW(), NOW())
                """), {"id": db_user_id, "email": f"{user_id}@slack.local", "name": user_name, "slack_id": user_id})

            conn.execute(text("""
                INSERT INTO decisions (id, organization_id, decision_number, status, created_by, source, slack_channel_id, created_at, updated_at)
                VALUES (:id, :org_id, :num, 'proposed', :user_id, 'slack', :channel_id, NOW(), NOW())
            """), {"id": decision_id, "org_id": org_id, "num": next_num, "user_id": db_user_id, "channel_id": channel_id})

            content = json.dumps({"context": f"Poll created from Slack by {user_name}", "choice": question, "rationale": "", "alternatives": []})
            conn.execute(text("""
                INSERT INTO decision_versions (id, decision_id, version_number, title, impact_level, content, tags, created_by, created_at)
                VALUES (:id, :did, 1, :title, 'medium', :content, '{}', :user_id, NOW())
            """), {"id": version_id, "did": decision_id, "title": question[:255], "content": content, "user_id": db_user_id})

            conn.execute(text("UPDATE decisions SET current_version_id = :vid WHERE id = :did"), {"vid": version_id, "did": decision_id})
            conn.commit()

            decision_number = next_num
            title = question[:255]

        # Get current votes
        result = conn.execute(text("""
            SELECT vote_type, external_user_name FROM poll_votes WHERE decision_id = :did
        """), {"did": decision_id})

        votes = {"agree": [], "concern": [], "block": []}
        for row in result.fetchall():
            vote_type, name = row[0], row[1] or "Someone"
            if vote_type in votes:
                votes[vote_type].append(name)

        return {"response_type": "in_channel", "blocks": SlackBlocks.consensus_poll(decision_id, decision_number, title, votes)}

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

    # Message shortcut (Log as Decision)
    if interaction_type == "message_action":
        callback_id = payload.get("callback_id")

        if callback_id == "log_message_as_decision":
            message = payload.get("message", {})
            channel = payload.get("channel", {})

            message_text = message.get("text", "")
            message_ts = message.get("ts", "")
            thread_ts = message.get("thread_ts")
            channel_id = channel.get("id", "")

            # Check duplicate
            if message_ts and channel_id:
                result = conn.execute(text("""
                    SELECT lm.decision_id, d.decision_number, dv.title
                    FROM logged_messages lm
                    JOIN decisions d ON lm.decision_id = d.id
                    JOIN decision_versions dv ON d.current_version_id = dv.id
                    WHERE lm.source = 'slack' AND lm.message_id = :msg_id AND lm.channel_id = :channel_id
                """), {"msg_id": message_ts, "channel_id": channel_id})
                existing = result.fetchone()

                if existing:
                    return {"response_type": "ephemeral", "blocks": SlackBlocks.duplicate_warning(str(existing[0]), existing[1], existing[2])}

            # Open modal
            if token and trigger_id:
                prefill_title = message_text.split("\n")[0][:100] if message_text else "Decision from Slack"
                modal = SlackModals.log_message(prefill_title, message_text, channel_id, message_ts, thread_ts)

                payload_data = json.dumps({"trigger_id": trigger_id, "view": modal}).encode()
                req = urllib.request.Request(
                    "https://slack.com/api/views.open",
                    data=payload_data,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                )
                try:
                    urllib.request.urlopen(req, timeout=10)
                except Exception:
                    pass

            return {}

        # AI Summarize Decision shortcut
        elif callback_id == "ai_summarize_decision":
            message = payload.get("message", {})
            channel = payload.get("channel", {})

            message_text = message.get("text", "")
            message_ts = message.get("ts", "")
            thread_ts = message.get("thread_ts") or message_ts  # Use message as thread root if not in thread
            channel_id = channel.get("id", "")
            channel_name = channel.get("name", "")

            # Check duplicate using thread_ts
            check_ts = thread_ts or message_ts
            if check_ts and channel_id:
                result = conn.execute(text("""
                    SELECT lm.decision_id, d.decision_number, dv.title
                    FROM logged_messages lm
                    JOIN decisions d ON lm.decision_id = d.id
                    JOIN decision_versions dv ON d.current_version_id = dv.id
                    WHERE lm.source = 'slack' AND lm.message_id = :msg_id AND lm.channel_id = :channel_id
                """), {"msg_id": check_ts, "channel_id": channel_id})
                existing = result.fetchone()

                if existing:
                    return {"response_type": "ephemeral", "blocks": SlackBlocks.duplicate_warning(str(existing[0]), existing[1], existing[2])}

            if not token:
                return {"response_type": "ephemeral", "text": ":x: Bot token not available."}

            # Check if AI is configured
            gemini_key = os.environ.get("GEMINI_API_KEY", "")
            if not gemini_key:
                # Fallback to regular log modal
                if trigger_id:
                    prefill_title = message_text.split("\n")[0][:100] if message_text else "Decision from Slack"
                    modal = SlackModals.log_message(prefill_title, message_text, channel_id, message_ts, thread_ts)
                    payload_data = json.dumps({"trigger_id": trigger_id, "view": modal}).encode()
                    req = urllib.request.Request(
                        "https://slack.com/api/views.open",
                        data=payload_data,
                        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                    )
                    try:
                        urllib.request.urlopen(req, timeout=10)
                    except Exception:
                        pass
                return {}

            try:
                # Fetch the thread
                if thread_ts and thread_ts != message_ts:
                    messages = fetch_slack_thread(token, channel_id, thread_ts)
                else:
                    # Just the single message
                    messages = [{"author": message.get("user", "Unknown"), "text": message_text, "timestamp": message_ts}]

                # Resolve user names
                messages = resolve_slack_user_names(token, messages)

                # Analyze with AI
                analysis = analyze_with_gemini(messages, channel_name)

                if not analysis:
                    # Fallback to regular modal if AI fails
                    prefill_title = message_text.split("\n")[0][:100] if message_text else "Decision from Slack"
                    modal = SlackModals.log_message(prefill_title, message_text, channel_id, message_ts, thread_ts)
                else:
                    # Use AI-prefilled modal
                    modal = SlackModals.ai_prefilled_modal(analysis, channel_id, message_ts, thread_ts)

                if trigger_id:
                    payload_data = json.dumps({"trigger_id": trigger_id, "view": modal}).encode()
                    req = urllib.request.Request(
                        "https://slack.com/api/views.open",
                        data=payload_data,
                        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                    )
                    try:
                        urllib.request.urlopen(req, timeout=10)
                    except Exception as e:
                        print(f"Failed to open modal: {e}")

            except Exception as e:
                print(f"AI analysis error: {e}")
                # Fallback to regular modal
                if trigger_id:
                    prefill_title = message_text.split("\n")[0][:100] if message_text else "Decision from Slack"
                    modal = SlackModals.log_message(prefill_title, message_text, channel_id, message_ts, thread_ts)
                    payload_data = json.dumps({"trigger_id": trigger_id, "view": modal}).encode()
                    req = urllib.request.Request(
                        "https://slack.com/api/views.open",
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

            # Get or create user
            result = conn.execute(text("SELECT id FROM users WHERE slack_user_id = :slack_id"), {"slack_id": user_id})
            user_row = result.fetchone()
            if user_row:
                db_user_id = str(user_row[0])
            else:
                db_user_id = str(uuid4())
                conn.execute(text("""
                    INSERT INTO users (id, email, name, slack_user_id, created_at, updated_at)
                    VALUES (:id, :email, :name, :slack_id, NOW(), NOW())
                """), {"id": db_user_id, "email": f"{user_id}@slack.local", "name": user_name, "slack_id": user_id})

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
                INSERT INTO decisions (id, organization_id, decision_number, status, created_by, source, slack_channel_id, slack_message_ts, slack_thread_ts, created_at, updated_at)
                VALUES (:id, :org_id, :num, :status, :user_id, 'slack', :channel_id, :msg_ts, :thread_ts, NOW(), NOW())
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
                """), {"id": str(uuid4()), "msg_id": check_ts, "channel_id": metadata.get("channel_id"), "did": decision_id})

            conn.commit()

            # Post confirmation to channel if we have one
            if token and metadata.get("channel_id"):
                msg_payload = json.dumps({
                    "channel": metadata.get("channel_id"),
                    "text": f"Decision logged: DEC-{next_num}",
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
                    SELECT d.decision_number, dv.title
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
                        "blocks": SlackBlocks.consensus_poll(decision_id, dec[0], dec[1], votes)
                    }

            # Help button
            if action_id == "show_help":
                return {"response_type": "ephemeral", "blocks": SlackBlocks.help_message()}

    return {}


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
    frontend_url = os.environ.get("FRONTEND_URL", "https://app.imputable.io")

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
                lines.append(f"- [DEC-{d[1]}: {d[2]}]({frontend_url}/decisions/{d[0]})")

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
                    # Verify signature
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

                    payload = json.loads(payload_str) if payload_str else {}
                    result = handle_slack_interactions(payload, conn)
                    self._send(200, result)

                # Teams
                elif platform == "teams":
                    activity = json.loads(body.decode()) if body else {}
                    result = handle_teams_activity(activity, conn)
                    self._send(200, result)

                else:
                    self._send(400, {"error": "Invalid platform or type parameter"})

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send(500, {"error": str(e)})
