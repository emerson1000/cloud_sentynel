"""
CloudSentinel - Azure Functions
Two timer-triggered serverless functions:
  1. daily_anomaly_check  — runs every day at 08:00 UTC
  2. weekly_report        — runs every Monday at 07:00 UTC

Deploy with: func azure functionapp publish <YOUR_APP_NAME>
"""

import os
import json
import logging
import asyncio
import azure.functions as func
from cryptography.fernet import Fernet

from core.azure_analyzer import AzureAnalyzer
from core.database import (
    get_active_connections,
    get_alert_config,
    save_report,
    log_notification,
    was_notified_today,
)
from core.notifications import (
    send_anomaly_notifications,
    send_weekly_report,
)

app = func.FunctionApp()
logger = logging.getLogger(__name__)

ENCRYPTION_KEY = os.environ["CLOUDSENTINEL_ENCRYPTION_KEY"].encode()
fernet = Fernet(ENCRYPTION_KEY)


def decrypt_secret(encrypted: str) -> str:
    return fernet.decrypt(encrypted.encode()).decode()


def encrypt_secret(plaintext: str) -> str:
    return fernet.encrypt(plaintext.encode()).decode()


def build_analyzer(conn: dict) -> AzureAnalyzer:
    return AzureAnalyzer(
        tenant_id=conn["tenant_id"],
        client_id=conn["client_id"],
        client_secret=decrypt_secret(conn["client_secret_encrypted"]),
        subscription_id=conn["subscription_id"],
    )


# ─── FUNCTION 1: Daily Anomaly Check ─────────────────────────────────────────
# Runs every day at 08:00 UTC — checks for spending spikes

@app.timer_trigger(
    schedule="0 0 8 * * *",  # cron: 08:00 UTC daily
    arg_name="myTimer",
    run_on_startup=False
)
async def daily_anomaly_check(myTimer: func.TimerRequest) -> None:
    logger.info("🔍 Daily anomaly check started")
    connections = get_active_connections()

    for conn in connections:
        conn_id = conn["id"]
        user_id = conn["user_id"]

        try:
            alert_config = get_alert_config(conn_id)
            if not alert_config:
                logger.info(f"No alert config for connection {conn_id}, skipping")
                continue

            threshold = float(alert_config.get("anomaly_threshold_pct", 15.0))
            analyzer = build_analyzer(conn)
            anomaly = analyzer.detect_anomaly(threshold_pct=threshold)

            if anomaly is None:
                logger.info(f"[{conn['display_name']}] No anomaly detected")
                continue

            logger.warning(f"[{conn['display_name']}] Anomaly: +{anomaly.delta_pct}%")

            # Deduplicate: only alert once per day per connection
            if was_notified_today(conn_id, "anomaly_alert"):
                logger.info(f"Already notified today for {conn_id}, skipping")
                continue

            # Get user email from profiles
            from core.database import get_db
            profile = get_db().table("profiles").select("email, tier").eq("id", user_id).single().execute()
            email = profile.data["email"]
            tier = profile.data.get("tier", "free")

            await send_anomaly_notifications(
                email=email,
                anomaly=anomaly.__dict__,
                subscription_id=conn["subscription_id"],
                alert_config=alert_config,
                tier=tier
            )

            log_notification(user_id, conn_id, "anomaly_alert", "email", anomaly.__dict__)

        except Exception as e:
            logger.error(f"Error processing connection {conn_id}: {e}", exc_info=True)

    logger.info("✅ Daily anomaly check complete")


# ─── FUNCTION 2: Weekly Full Report ──────────────────────────────────────────
# Runs every Monday at 07:00 UTC — full report with orphans + suggestions

@app.timer_trigger(
    schedule="0 0 7 * * 1",  # cron: 07:00 UTC every Monday
    arg_name="myTimer",
    run_on_startup=False
)
async def weekly_report(myTimer: func.TimerRequest) -> None:
    logger.info("📊 Weekly report generation started")
    connections = get_active_connections()

    for conn in connections:
        conn_id = conn["id"]
        user_id = conn["user_id"]

        try:
            alert_config = get_alert_config(conn_id)

            from core.database import get_db
            profile = get_db().table("profiles").select("email, tier").eq("id", user_id).single().execute()
            email = profile.data["email"]
            tier = profile.data.get("tier", "free")

            analyzer = build_analyzer(conn)
            report = analyzer.generate_full_report()

            saved = save_report(conn_id, user_id, "weekly", report)
            logger.info(f"[{conn['display_name']}] Report saved: {saved.get('id')}")

            if alert_config:
                await send_weekly_report(email, report, alert_config, tier)
                log_notification(user_id, conn_id, "weekly_report", "email", {
                    "report_id": saved.get("id"),
                    "total_spend": report.get("total_spend_30d"),
                    "savings": report.get("total_potential_savings")
                })

        except Exception as e:
            logger.error(f"Error generating weekly report for {conn_id}: {e}", exc_info=True)

    logger.info("✅ Weekly reports complete")


# ─── FUNCTION 3: On-Demand HTTP Trigger (Pro tier) ───────────────────────────
# POST /api/scan — triggers immediate scan for Pro users

@app.route(route="scan", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
async def on_demand_scan(req: func.HttpRequest) -> func.HttpResponse:
    """
    Called by the Next.js frontend when a Pro user clicks "Scan Now".
    Expects: { "connection_id": "...", "user_id": "..." }
    Validates via Supabase JWT before proceeding.
    """
    try:
        body = req.get_json()
        connection_id = body.get("connection_id")
        user_id = body.get("user_id")

        if not connection_id or not user_id:
            return func.HttpResponse(
                json.dumps({"error": "connection_id and user_id are required"}),
                status_code=400,
                mimetype="application/json"
            )

        # Validate JWT and tier check
        from core.database import get_db
        db = get_db()
        profile = db.table("profiles").select("tier").eq("id", user_id).single().execute()
        tier = profile.data.get("tier", "free")

        if tier == "free":
            return func.HttpResponse(
                json.dumps({"error": "On-demand scans require Pro tier"}),
                status_code=403,
                mimetype="application/json"
            )

        conn = db.table("cloud_connections").select("*").eq("id", connection_id).eq("user_id", user_id).single().execute()
        if not conn.data:
            return func.HttpResponse(
                json.dumps({"error": "Connection not found"}),
                status_code=404,
                mimetype="application/json"
            )

        analyzer = build_analyzer(conn.data)
        report = analyzer.generate_full_report()
        saved = save_report(connection_id, user_id, "on_demand", report)

        return func.HttpResponse(
            json.dumps({"success": True, "report_id": saved.get("id"), "report": report}),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        logger.error(f"On-demand scan error: {e}", exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": "Internal server error"}),
            status_code=500,
            mimetype="application/json"
        )
