"""
Slack Integration Configuration.

Environment variables required:
- SLACK_BOT_TOKEN: Bot User OAuth Token (xoxb-...)
- SLACK_SIGNING_SECRET: For verifying Slack requests
- SLACK_APP_TOKEN: For Socket Mode (optional)
- APP_BASE_URL: Your application's base URL
"""

import os
from dataclasses import dataclass


@dataclass
class SlackConfig:
    """Configuration for Slack integration."""

    bot_token: str
    signing_secret: str
    app_token: str | None
    app_base_url: str

    # Link unfurling domains
    unfurl_domains: list[str]

    @classmethod
    def from_env(cls) -> "SlackConfig":
        """Load configuration from environment variables."""
        bot_token = os.environ.get("SLACK_BOT_TOKEN", "")
        if not bot_token:
            raise ValueError("SLACK_BOT_TOKEN environment variable is required")

        signing_secret = os.environ.get("SLACK_SIGNING_SECRET", "")
        if not signing_secret:
            raise ValueError("SLACK_SIGNING_SECRET environment variable is required")

        app_base_url = os.environ.get("APP_BASE_URL", "https://ledger.app")

        # Domains to unfurl (extract from base URL + any custom domains)
        base_domain = app_base_url.replace("https://", "").replace("http://", "").split("/")[0]
        unfurl_domains = [base_domain]

        # Add any additional domains from env
        extra_domains = os.environ.get("SLACK_UNFURL_DOMAINS", "")
        if extra_domains:
            unfurl_domains.extend(extra_domains.split(","))

        return cls(
            bot_token=bot_token,
            signing_secret=signing_secret,
            app_token=os.environ.get("SLACK_APP_TOKEN"),
            app_base_url=app_base_url,
            unfurl_domains=unfurl_domains,
        )


def get_slack_config() -> SlackConfig:
    """Get Slack configuration singleton."""
    return SlackConfig.from_env()
