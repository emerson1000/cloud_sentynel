"""
CloudSentinel - FastAPI REST API (v2)

Scan logic:
- POST /api/scan/{connection_id}   → on-demand scan (quota enforced)
- POST /api/connections            → saves connection + triggers first scan automatically
- Azure Function (function_app.py) → weekly scan every Monday 7am (no quota consumed)

Quota rules:
- free       → 0 on-demand scans/week (weekly auto only)
- pro        → 2 on-demand scans/week
- enterprise → unlimited
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator

from core.database import (
    get_db, save_report, get_recent_reports,
    get_dashboard_summary, decrypt_credentials, save_connection,
)
from core.base_analyzer import create_analyzer

logger = logging.getLogger(__name__)
app    = FastAPI(title="CloudSentinel API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins   = [os.environ.get("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials = True,
    allow_methods   = ["*"],
    allow_headers   = ["*"],
)

TIER_SCAN_LIMITS = {"free": 0, "pro": 2, "enterprise": -1}


# ── Auth ───────────────────────────────────────────────────────────────────────

async def get_current_user(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization[7:]
    from supabase import create_client
    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])
    try:
        return client.auth.get_user(token).user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ── Quota helpers ──────────────────────────────────────────────────────────────

def get_week_start() -> str:
    """Return the Monday of the current week as YYYY-MM-DD."""
    today = datetime.now(timezone.utc).date()
    return str(today - timedelta(days=today.weekday()))

def check_scan_quota(user_id: str) -> dict:
    """Returns {allowed, used, limit, reason?} using Supabase RPC."""
    result = get_db().rpc("can_user_scan", {"p_user_id": user_id}).execute()
    return result.data

def consume_scan_quota(user_id: str):
    """Increment the weekly on-demand scan counter."""
    get_db().rpc("consume_scan_quota", {"p_user_id": user_id}).execute()


# ── Core scan logic ────────────────────────────────────────────────────────────

def run_scan(connection_id: str, user_id: str, report_type: str = "on_demand") -> dict:
    """
    Fetch credentials, run the appropriate analyzer, save lightweight report.
    Returns the full FullReport dict (including resource lists) for the API response.
    The DB only stores the summary — not the full lists.
    """
    db     = get_db()
    result = db.table("cloud_connections").select("*") \
               .eq("id", connection_id).eq("user_id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Connection not found")

    conn  = result.data[0]
    creds = decrypt_credentials(conn["credentials_encrypted"])

    # Build the right analyzer for this provider
    analyzer = create_analyzer(conn["provider"], creds)

    # Validate credentials are still working
    ok, msg = analyzer.test_connection()
    if not ok:
        raise HTTPException(status_code=400, detail=f"Cloud connection error: {msg}")

    # Run full scan
    logger.info(f"[{conn['provider'].upper()}] Starting {report_type} scan for connection {connection_id}")
    report = analyzer.generate_full_report()
    report_dict = report.to_dict()

    # Save lightweight summary to DB
    now = datetime.now(timezone.utc)
    save_report(
        connection_id = connection_id,
        user_id       = user_id,
        provider      = conn["provider"],
        report_type   = report_type,
        report_data   = report_dict,
        period_start  = str((now - timedelta(days=30)).date()),
        period_end    = str(now.date()),
    )

    return report_dict


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


# ── Scan quota status ──────────────────────────────────────────────────────────

@app.get("/api/scan/quota")
async def get_scan_quota(user=Depends(get_current_user)):
    """
    Returns current week's scan usage for the dashboard button.
    Frontend uses this to show "1/2 scans used" or disable the button.
    """
    quota = check_scan_quota(user.id)
    return {
        "allowed":    quota.get("allowed", False),
        "used":       quota.get("used", 0),
        "limit":      quota.get("limit", 0),
        "tier":       quota.get("tier", "free"),
        "week_start": get_week_start(),
        "resets_on":  str(
            datetime.now(timezone.utc).date()
            + timedelta(days=7 - datetime.now(timezone.utc).weekday())
        ),
        "reason": quota.get("reason"),
    }


# ── On-demand scan ─────────────────────────────────────────────────────────────

@app.post("/api/scan/{connection_id}")
async def trigger_scan(connection_id: str, user=Depends(get_current_user)):
    """
    On-demand scan — enforces weekly quota per tier:
    - free:       blocked (0/week)
    - pro:        2/week
    - enterprise: unlimited
    """
    quota = check_scan_quota(user.id)

    if not quota.get("allowed"):
        raise HTTPException(
            status_code=429,
            detail={
                "error":   "quota_exceeded",
                "message": quota.get("reason", "Scan limit reached."),
                "used":    quota.get("used", 0),
                "limit":   quota.get("limit", 0),
                "tier":    quota.get("tier", "free"),
            }
        )

    # Consume quota BEFORE running scan (prevents double-clicking abuse)
    consume_scan_quota(user.id)

    try:
        report_data = run_scan(connection_id, user.id, report_type="on_demand")
    except HTTPException:
        # Refund quota if scan itself failed (connection error, bad creds, etc.)
        # We do this by decrementing — simple approach
        db = get_db()
        week = get_week_start()
        db.table("scan_quota").update({"scans_used": max(0, quota["used"])}) \
          .eq("user_id", user.id).eq("week_start", week).execute()
        raise

    return {
        "success":    True,
        "report":     report_data,
        "quota_used": quota.get("used", 0) + 1,
        "quota_limit": quota.get("limit", 0),
    }


# ── Connections ────────────────────────────────────────────────────────────────

class AddConnectionRequest(BaseModel):
    provider:     str
    display_name: str
    credentials:  dict   # provider-specific, validated in save_connection()

    @validator("provider")
    def validate_provider(cls, v):
        if v not in ("azure", "aws", "gcp"):
            raise ValueError("Provider must be azure, aws, or gcp")
        return v


@app.get("/api/connections")
async def list_connections(user=Depends(get_current_user)):
    db     = get_db()
    result = db.table("cloud_connections").select(
        "id, display_name, provider, account_identifier, is_active, last_scan_at, created_at"
    ).eq("user_id", user.id).eq("is_active", True).order("created_at", desc=True).execute()
    return result.data or []


@app.post("/api/connections")
async def add_connection(
    body: AddConnectionRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
):
    """
    Save a new cloud connection and trigger the FIRST scan automatically.
    The first scan is always free (report_type='initial') — quota not consumed.
    """
    # Validate + encrypt + save
    creds = body.credentials
    account_id = (
        creds.get("subscription_id") or   # Azure
        creds.get("account_id") or         # AWS
        creds.get("project_id") or         # GCP
        "unknown"
    )

    conn = save_connection(
        user_id            = user.id,
        provider           = body.provider,
        display_name       = body.display_name,
        account_identifier = account_id,
        credentials        = creds,
    )

    # Trigger first scan in background — user sees dashboard immediately
    # while scan runs. Dashboard will refresh when done.
    background_tasks.add_task(
        run_scan,
        connection_id = conn["id"],
        user_id       = user.id,
        report_type   = "initial",
    )

    return {"success": True, "connection": conn, "scan_started": True}


@app.delete("/api/connections/{connection_id}")
async def delete_connection(connection_id: str, user=Depends(get_current_user)):
    get_db().table("cloud_connections").update({"is_active": False}) \
        .eq("id", connection_id).eq("user_id", user.id).execute()
    return {"success": True}


# ── Reports ────────────────────────────────────────────────────────────────────

@app.get("/api/reports")
async def list_reports(connection_id: Optional[str] = None, user=Depends(get_current_user)):
    return get_recent_reports(user.id, connection_id, limit=20)


@app.get("/api/reports/{report_id}")
async def get_report(report_id: str, user=Depends(get_current_user)):
    db     = get_db()
    result = db.table("reports").select("*").eq("id", report_id).eq("user_id", user.id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Report not found")
    report = result.data
    if isinstance(report.get("report_data"), str):
        report["report_data"] = json.loads(report["report_data"])
    return report


@app.get("/api/dashboard/summary")
async def dashboard_summary(user=Depends(get_current_user)):
    return get_dashboard_summary(user.id)


# ── Settings ───────────────────────────────────────────────────────────────────

class AlertConfigRequest(BaseModel):
    anomaly_threshold_pct: float = 15.0
    notify_email:          bool  = True
    notify_telegram:       bool  = False
    telegram_chat_id:      Optional[str] = None

@app.put("/api/settings/alerts")
async def update_alert_config(body: AlertConfigRequest, user=Depends(get_current_user)):
    config = {
        "threshold":        body.anomaly_threshold_pct,
        "email":            body.notify_email,
        "telegram":         body.notify_telegram,
        "chat_id":          body.telegram_chat_id or "",
    }
    get_db().table("profiles").update({"notification_config": config}) \
        .eq("id", user.id).execute()
    return {"success": True}
