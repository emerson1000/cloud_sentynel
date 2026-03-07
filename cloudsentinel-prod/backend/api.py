"""
CloudSentinel - FastAPI REST API
Serves the Next.js dashboard. Handles connection management, report retrieval, and settings.

Run locally: uvicorn api:app --reload --port 8000
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
from cryptography.fernet import Fernet

from core.database import (
    get_db,
    save_report,
    get_recent_reports,
    get_alert_config,
)
from core.azure_analyzer import AzureAnalyzer

logger = logging.getLogger(__name__)
app = FastAPI(title="CloudSentinel API", version="1.0.0")

fernet = Fernet(os.environ["CLOUDSENTINEL_ENCRYPTION_KEY"].encode())

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── AUTH DEPENDENCY ──────────────────────────────────────────────────────────

async def get_current_user(authorization: str = Header(...)):
    """Validate Supabase JWT token."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization[7:]
    from supabase import create_client
    from core.database import SUPABASE_URL

    # Use the anon key here to validate JWT
    anon_key = os.environ["SUPABASE_ANON_KEY"]
    client = create_client(SUPABASE_URL, anon_key)
    try:
        user = client.auth.get_user(token)
        return user.user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ─── SCHEMAS ──────────────────────────────────────────────────────────────────

class AddConnectionRequest(BaseModel):
    display_name: str
    subscription_id: str
    tenant_id: str
    client_id: str
    client_secret: str  # plaintext — encrypted before storing

    @validator("subscription_id")
    def validate_subscription_id(cls, v):
        import re
        if not re.match(r'^[0-9a-f-]{36}$', v.lower()):
            raise ValueError("Invalid Azure Subscription ID format")
        return v


class UpdateAlertConfigRequest(BaseModel):
    connection_id: str
    anomaly_threshold_pct: float = 15.0
    notify_email: bool = True
    notify_telegram: bool = False
    telegram_chat_id: Optional[str] = None


# ─── ENDPOINTS ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/connections")
async def list_connections(user=Depends(get_current_user)):
    db = get_db()
    result = db.table("cloud_connections").select(
        "id, display_name, provider, subscription_id, is_active, last_scan_at, created_at"
        # Note: client_secret_encrypted is NOT returned
    ).eq("user_id", user.id).order("created_at", desc=True).execute()
    return result.data or []


@app.post("/api/connections")
async def add_connection(body: AddConnectionRequest, user=Depends(get_current_user)):
    db = get_db()

    # Test the credentials before saving
    try:
        analyzer = AzureAnalyzer(
            tenant_id=body.tenant_id,
            client_id=body.client_id,
            client_secret=body.client_secret,
            subscription_id=body.subscription_id
        )
        # Lightweight validation: just list resource groups
        list(analyzer.resource_client.resource_groups.list())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Azure credential validation failed: {str(e)}")

    encrypted_secret = fernet.encrypt(body.client_secret.encode()).decode()

    result = db.table("cloud_connections").insert({
        "user_id": user.id,
        "display_name": body.display_name,
        "provider": "azure",
        "subscription_id": body.subscription_id,
        "tenant_id": body.tenant_id,
        "client_id": body.client_id,
        "client_secret_encrypted": encrypted_secret,
        "is_active": True,
    }).execute()

    conn_id = result.data[0]["id"]

    # Create default alert config
    db.table("alert_configs").insert({
        "connection_id": conn_id,
        "user_id": user.id,
        "anomaly_threshold_pct": 15.0,
        "notify_email": True,
        "notify_telegram": False,
        "is_active": True
    }).execute()

    conn = result.data[0].copy()
    conn.pop("client_secret_encrypted", None)
    return {"success": True, "connection": conn}


@app.delete("/api/connections/{connection_id}")
async def delete_connection(connection_id: str, user=Depends(get_current_user)):
    db = get_db()
    db.table("cloud_connections").update({"is_active": False}).eq("id", connection_id).eq("user_id", user.id).execute()
    return {"success": True}


@app.get("/api/reports")
async def list_reports(connection_id: Optional[str] = None, user=Depends(get_current_user)):
    reports = get_recent_reports(user.id, connection_id, limit=20)
    return reports


@app.get("/api/reports/{report_id}")
async def get_report(report_id: str, user=Depends(get_current_user)):
    db = get_db()
    result = db.table("reports").select("*").eq("id", report_id).eq("user_id", user.id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Report not found")
    report = result.data
    # Parse JSON blob
    if isinstance(report.get("report_data"), str):
        report["report_data"] = json.loads(report["report_data"])
    return report


@app.get("/api/dashboard/summary")
async def get_dashboard_summary(user=Depends(get_current_user)):
    """
    Aggregate summary across all connections for the dashboard overview.
    Returns totals and the latest report per connection.
    """
    db = get_db()

    connections = db.table("cloud_connections").select("id, display_name, last_scan_at").eq(
        "user_id", user.id
    ).eq("is_active", True).execute().data or []

    total_spend = 0
    total_savings = 0
    total_orphans = 0
    latest_reports = []

    for conn in connections:
        reports = get_recent_reports(user.id, conn["id"], limit=1)
        if reports:
            r = reports[0]
            total_spend += float(r.get("total_spend") or 0)
            total_savings += float(r.get("total_savings_identified") or 0)
            total_orphans += int(r.get("orphan_count") or 0)
            latest_reports.append({**r, "connection_name": conn["display_name"]})

    profile = db.table("profiles").select("tier, full_name").eq("id", user.id).single().execute()

    return {
        "total_spend_30d": round(total_spend, 2),
        "total_savings_identified": round(total_savings, 2),
        "total_orphan_count": total_orphans,
        "connection_count": len(connections),
        "latest_reports": latest_reports,
        "tier": profile.data.get("tier", "free") if profile.data else "free"
    }


@app.put("/api/alert-config")
async def update_alert_config(body: UpdateAlertConfigRequest, user=Depends(get_current_user)):
    db = get_db()
    existing = db.table("alert_configs").select("id").eq("connection_id", body.connection_id).eq("user_id", user.id).execute()

    data = {
        "anomaly_threshold_pct": body.anomaly_threshold_pct,
        "notify_email": body.notify_email,
        "notify_telegram": body.notify_telegram,
        "telegram_chat_id": body.telegram_chat_id,
        "is_active": True
    }

    if existing.data:
        db.table("alert_configs").update(data).eq("id", existing.data[0]["id"]).execute()
    else:
        db.table("alert_configs").insert({**data, "connection_id": body.connection_id, "user_id": user.id}).execute()

    return {"success": True}
