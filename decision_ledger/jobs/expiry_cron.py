"""
Expiry Cron Job: Daily processing of tech debt timers.

This module runs as a scheduled job (via cron, Celery, or similar)
to process decision expiry and send notifications.

Typical cron schedule: 0 9 * * * (daily at 9 AM)
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from ..services.expiry_engine import ExpiryEngine, ExpiryConfig
from ..services.notification_service import NotificationService, EmailConfig


logger = logging.getLogger(__name__)


async def run_expiry_job(
    database_url: str,
    email_config: EmailConfig | None = None,
    expiry_config: ExpiryConfig | None = None,
) -> dict[str, Any]:
    """
    Main entry point for the expiry cron job.

    This function:
    1. Processes status transitions (AT_RISK, EXPIRED)
    2. Generates reminder notifications
    3. Sends pending notifications
    4. Logs results

    Args:
        database_url: PostgreSQL connection string
        email_config: Email delivery configuration
        expiry_config: Expiry threshold configuration

    Returns:
        Job result summary
    """
    start_time = datetime.now(timezone.utc)
    logger.info(f"Starting expiry job at {start_time.isoformat()}")

    # Create database session
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    results = {
        "started_at": start_time.isoformat(),
        "completed_at": None,
        "expired_count": 0,
        "at_risk_count": 0,
        "notifications_generated": 0,
        "notifications_sent": 0,
        "notifications_failed": 0,
        "errors": [],
    }

    try:
        async with session_factory() as session:
            async with session.begin():
                # Step 1: Process status transitions
                expiry_engine = ExpiryEngine(
                    session,
                    config=expiry_config or ExpiryConfig(),
                )

                expired_count, at_risk_count = await expiry_engine.process_expiry_transitions()
                results["expired_count"] = expired_count
                results["at_risk_count"] = at_risk_count

                logger.info(
                    f"Status transitions: {expired_count} expired, {at_risk_count} at risk"
                )

                # Step 2: Generate reminder notifications
                notification_batch = await expiry_engine.generate_reminder_notifications()
                results["notifications_generated"] = len(notification_batch.notifications)
                results["errors"].extend(notification_batch.errors)

                logger.info(
                    f"Generated {len(notification_batch.notifications)} notifications "
                    f"for {notification_batch.decisions_processed} decisions"
                )

                # Commit status transitions and notification records
                await session.commit()

        # Step 3: Send pending notifications (in separate transaction)
        async with session_factory() as session:
            async with session.begin():
                notification_service = NotificationService(
                    session,
                    email_config=email_config,
                )

                sent, failed, errors = await notification_service.process_pending_notifications()
                results["notifications_sent"] = sent
                results["notifications_failed"] = failed
                results["errors"].extend(errors)

                logger.info(f"Sent {sent} notifications, {failed} failed")

                await session.commit()

    except Exception as e:
        logger.error(f"Expiry job failed: {str(e)}")
        results["errors"].append(f"Job failed: {str(e)}")
        raise

    finally:
        await engine.dispose()

    end_time = datetime.now(timezone.utc)
    results["completed_at"] = end_time.isoformat()
    results["duration_seconds"] = (end_time - start_time).total_seconds()

    logger.info(
        f"Expiry job completed in {results['duration_seconds']:.2f}s: "
        f"{results['expired_count']} expired, {results['at_risk_count']} at risk, "
        f"{results['notifications_sent']} notifications sent"
    )

    return results


# =============================================================================
# CLI ENTRY POINT
# =============================================================================


def main():
    """CLI entry point for the expiry job."""
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Run the decision expiry cron job")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL connection string",
    )
    parser.add_argument(
        "--at-risk-days",
        type=int,
        default=14,
        help="Days before expiry to mark as AT_RISK",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be done without making changes",
    )

    args = parser.parse_args()

    if not args.database_url:
        print("Error: DATABASE_URL is required")
        exit(1)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run the job
    expiry_config = ExpiryConfig(at_risk_threshold_days=args.at_risk_days)

    try:
        results = asyncio.run(run_expiry_job(
            database_url=args.database_url,
            expiry_config=expiry_config,
        ))
        print(f"Job completed: {results}")
    except Exception as e:
        print(f"Job failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()
