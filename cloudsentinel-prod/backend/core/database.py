"""
CloudSentinel - Supabase Database Layer (Multi-Cloud)
Supports Azure, AWS, and GCP connections in the same schema.
Each provider stores different credential fields — handled via JSONB.
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from supabase import create_client, Client

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

_client: Optional[Client] = None


def get_db() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


# ─── SCHEMA SQL ───────────────────────────────────────────────────────────────
# Run this in your Supabase SQL Editor once to set up the schema.

SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    tier TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'pro', 'team')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Multi-cloud connections
-- Credentials are stored as an ENCRYPTED JSONB blob (encrypted at app layer with Fernet)
-- Each provider has a different credential shape:
--   Azure:  { tenant_id, client_id, client_secret, subscription_id }
--   AWS:    { aws_access_key_id, aws_secret_access_key, aws_region, account_id }
--   GCP:    { service_account_json, project_id, billing_account_id }
CREATE TABLE IF NOT EXISTS cloud_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    provider TEXT NOT NULL CHECK (provider IN ('azure', 'aws', 'gcp')),
    display_name TEXT NOT NULL,
    -- Provider-specific identity fields (NOT secret — safe to store plain)
    account_identifier TEXT NOT NULL,  -- subscription_id / AWS account_id / GCP project_id
    region TEXT,                        -- primary region (AWS/GCP)
    -- All sensitive credentials go here, encrypted with Fernet before insert
    credentials_encrypted TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_scan_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connection_id UUID NOT NULL REFERENCES cloud_connections(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    provider TEXT NOT NULL CHECK (provider IN ('azure', 'aws', 'gcp')),
    report_type TEXT NOT NULL CHECK (report_type IN ('weekly', 'daily_anomaly', 'on_demand')),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    total_spend NUMERIC(12,2),
    total_savings_identified NUMERIC(12,2),
    orphan_count INTEGER DEFAULT 0,
    anomaly_detected BOOLEAN DEFAULT FALSE,
    report_data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alert_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connection_id UUID NOT NULL REFERENCES cloud_connections(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    anomaly_threshold_pct NUMERIC(5,2) NOT NULL DEFAULT 15.0,
    notify_email BOOLEAN NOT NULL DEFAULT TRUE,
    notify_telegram BOOLEAN NOT NULL DEFAULT FALSE,
    telegram_chat_id TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS notification_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    connection_id UUID NOT NULL REFERENCES cloud_connections(id) ON DELETE CASCADE,
    notification_type TEXT NOT NULL,
    channel TEXT NOT NULL CHECK (channel IN ('email', 'telegram')),
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB
);

CREATE INDEX IF NOT EXISTS idx_reports_user_id ON reports(user_id);
CREATE INDEX IF NOT EXISTS idx_reports_connection_id ON reports(connection_id);
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_connections_user_provider ON cloud_connections(user_id, provider);

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE cloud_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own profile"       ON profiles           FOR ALL USING (auth.uid() = id);
CREATE POLICY "Users see own connections"   ON cloud_connections  FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users see own reports"       ON reports            FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users see own alert configs" ON alert_configs      FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users see own notifications" ON notification_log   FOR ALL USING (auth.uid() = user_id);
"""


# ─── CREDENTIAL HELPERS ───────────────────────────────────────────────────────

def encrypt_credentials(credentials: dict, fernet) -> str:
    """Serialize and encrypt a credentials dict before storing."""
    return fernet.encrypt(json.dumps(credentials).encode()).decode()


def decrypt_credentials(encrypted: str, fernet) -> dict:
    """Decrypt and deserialize credentials from the DB."""
    return json.loads(fernet.decrypt(encrypted.encode()).decode())


# ─── DB OPERATIONS ────────────────────────────────────────────────────────────

def save_report(connection_id: str, user_id: str, provider: str, report_type: str, report_data: dict) -> dict:
    db = get_db()
    all_orphans = [r for cat in report_data.get("orphan_resources", {}).values() for r in cat]

    from datetime import timedelta
    row = {
        "connection_id": connection_id,
        "user_id": user_id,
        "provider": provider,
        "report_type": report_type,
        "period_start": (datetime.now(timezone.utc).date() - timedelta(days=30)).isoformat(),
        "period_end": datetime.now(timezone.utc).date().isoformat(),
        "total_spend": report_data.get("total_spend_30d", 0),
        "total_savings_identified": report_data.get("total_potential_savings", 0),
        "orphan_count": len(all_orphans),
        "anomaly_detected": report_data.get("anomaly_alert") is not None,
        "report_data": json.dumps(report_data),
    }

    result = db.table("reports").insert(row).execute()
    db.table("cloud_connections").update(
        {"last_scan_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", connection_id).execute()

    return result.data[0] if result.data else {}


def get_active_connections() -> list[dict]:
    db = get_db()
    result = db.table("cloud_connections").select("*").eq("is_active", True).execute()
    return result.data or []


def get_alert_config(connection_id: str) -> Optional[dict]:
    db = get_db()
    result = db.table("alert_configs").select("*").eq("connection_id", connection_id).eq("is_active", True).execute()
    return result.data[0] if result.data else None


def log_notification(user_id: str, connection_id: str, notification_type: str, channel: str, payload: dict):
    db = get_db()
    db.table("notification_log").insert({
        "user_id": user_id,
        "connection_id": connection_id,
        "notification_type": notification_type,
        "channel": channel,
        "payload": json.dumps(payload),
    }).execute()


def was_notified_today(connection_id: str, notification_type: str) -> bool:
    db = get_db()
    today = datetime.now(timezone.utc).date().isoformat()
    result = db.table("notification_log").select("id").eq(
        "connection_id", connection_id
    ).eq(
        "notification_type", notification_type
    ).gte("sent_at", f"{today}T00:00:00Z").execute()
    return len(result.data) > 0


def get_recent_reports(user_id: str, connection_id: Optional[str] = None, limit: int = 10) -> list[dict]:
    db = get_db()
    query = db.table("reports").select(
        "id, provider, report_type, period_start, period_end, total_spend, "
        "total_savings_identified, orphan_count, anomaly_detected, created_at"
    ).eq("user_id", user_id).order("created_at", desc=True).limit(limit)

    if connection_id:
        query = query.eq("connection_id", connection_id)

    return query.execute().data or []
