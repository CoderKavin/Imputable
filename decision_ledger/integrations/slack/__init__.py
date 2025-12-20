"""
Slack Integration for Decision Ledger.

This module provides:
- Slash command handling (/decision search)
- Link unfurling for rich previews
- Direct message notifications for expired decisions
"""

from .client import SlackClient
from .handlers import SlackEventHandler
from .blocks import BlockBuilder

__all__ = ["SlackClient", "SlackEventHandler", "BlockBuilder"]
