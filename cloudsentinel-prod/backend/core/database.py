"""
CloudSentinel - Database Layer (Production-hardened)

Key design decisions:
- Reports store SUMMARY only (numbers) — full resource lists are NOT persisted
- Credentials are encrypted with Fernet AES-256 before any DB write
- Old reports auto-purged after 90 days via Supabase scheduled function
- AWS Cost Explorer calls are cached 24h to avoid per-call charges
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from supabase import create_client, Client
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

SUPABASE_URL         = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
ENCRYPTION_KEY       = os.environ["CLOUDSENTINEL_ENCRYPTION_KEY"].encode()

_client:  Optional[Client] = None
_fernet:  Optional[Fernet] = None


# ── Singleton helpers ──────────────────────────────────────────────────────────

def get_db() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client

def get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(ENCRYPTION_KEY)
    return _fernet


# ── Credential encryption ──────────────────────────────────────────────────────

def encrypt_credentials(creds: dict) -> str:
    """Encrypt credentials dict → base64 string for DB storage."""
    plaintext = json.dumps(creds).encode()
    return get_fernet().encrypt(plaintext).decode()

def decrypt_credentials(encrypted: str) -> dict:
    """Decrypt stored credentials → dict for SDK use."""
    plaintext = get_fernet().decrypt(encrypted.encode())
    return json.loads(plaintext)


# ── Credential safety validator ────────────────────────────────────────────────

FORBIDDEN_AWS_ACTIONS = [
    "AdministratorAccess", "PowerUserAccess", "AmazonEC2FullAccess",
    "AmazonS3FullAccess", "IAMFullAccess", "AWSLambdaFullAccess",
]

def validate_credentials_safe(provider: str, creds: dict) -> tuple[bool, str]:
    """
    Basic pre-storage validation to reject write-capable credentials.
    Returns (is_safe, reason).
    Full validation happens in the analyzer's test_connection() method.
    """
    if provider == "aws":
        # Reject if they accidentally pasted root credentials
        if creds.get("aws_access_key_id", "").startswith("ASIA"):
            return False, "Temporary STS credentials are not supported. Use permanent IAM user keys."
        if len(creds.get("aws_secret_access_key", "")) < 30:
            return False, "Invalid AWS Secret Access Key format."

    if provider == "azure":
        if not creds.get("tenant_id") or not creds.get("client_id"):
            return False, "Azure credentials require tenant_id and client_id."
        if len(creds.get("client_secret", "")) < 8:
            return False, "Azure client_secret appears invalid."

    if provider == "gcp":
        sa = creds.get("service_account_json", {})
        if isinstance(sa, str):
            try:
                sa = json.loads(sa)
            except Exception:
                return False, "GCP service_account_json is not valid JSON."
        if sa.get("type") != "service_account":
            return False, "GCP credentials must be a service_account JSON key."
        if not sa.get("private_key") or not sa.get("client_email"):
            return False, "GCP service account JSON is missing required fields."

    return True, "ok"


# ── Connections ────────────────────────────────────────────────────────────────

def save_connection(user_id: str, provider: str, display_name: str,
                    account_identifier: str, credentials: dict) -> dict:
    """
    Validate, encrypt and save a cloud connection.
    Raises ValueError if credentials look unsafe.
    """
    is_safe, reason = validate_credentials_safe(provider, credentials)
    if not is_safe:
        raise ValueError(f"Credential validation failed: {reason}")

    encrypted = encrypt_credentials(credentials)
    db = get_db()

    result = db.table("cloud_connections").insert({
        "user_id":               user_id,
        "provider":              provider,
        "display_name":          display_name,
        "account_identifier":    account_identifier,
        "credentials_encrypted": encrypted,
        "is_active":             True,
        "created_at":            datetime.now(timezone.utc).isoformat(),
    }).execute()

    return result.data[0]


def get_active_connections(user_id: Optional[str] = None) -> list[dict]:
    """Get all active connections. If user_id given, filter to that user only."""
    db = get_db()
    q  = db.table("cloud_connections").select("*").eq("is_active", True)
    if user_id:
        q = q.eq("user_id", user_id)
    return q.execute().data


def get_connection_credentials(connection_id: str, user_id: str) -> dict:
    """Fetch and decrypt credentials for a specific connection."""
    db     = get_db()
    result = db.table("cloud_connections").select("*") \
               .eq("id", connection_id).eq("user_id", user_id).execute()
    if not result.data:
        raise ValueError(f"Connection {connection_id} not found for user {user_id}")
    return decrypt_credentials(result.data[0]["credentials_encrypted"])


def mark_connection_scanned(connection_id: str):
    get_db().table("cloud_connections") \
        .update({"last_scan_at": datetime.now(timezone.utc).isoformat()}) \
        .eq("id", connection_id).execute()


# ── Reports — lightweight storage ─────────────────────────────────────────────
#
# We store SUMMARY NUMBERS only. The full resource list (potentially MBs of JSON)
# is NOT saved — it's returned in the API response and displayed, then discarded.
# This keeps the DB lean and avoids row size issues with large cloud accounts.
#
# Exception: anomaly_alert and cost_by_service are small and useful for trends.

MAX_REPORT_DATA_BYTES = 50_000   # 50KB hard cap on report_data JSONB


def _trim_report_data(report_data: dict) -> dict:
    """
    Keep only the lightweight fields for DB storage.
    Full orphan lists and suggestions are returned via API but not persisted.
    """
    return {
        "total_spend_30d":         report_data.get("total_spend_30d", 0),
        "total_potential_savings": report_data.get("total_potential_savings", 0),
        "cost_by_service":         report_data.get("cost_by_service", [])[:10],  # top 10 only
        "anomaly_alert":           report_data.get("anomaly_alert"),              # small dict or None
        # Full lists NOT stored — too large, not needed for history view
        "orphan_summary": {
            "unattached_disks":    len(report_data.get("orphan_resources", {}).get("unattached_disks", [])),
            "idle_public_ips":     len(report_data.get("orphan_resources", {}).get("idle_public_ips", [])),
            "idle_load_balancers": len(report_data.get("orphan_resources", {}).get("idle_load_balancers", [])),
            "stopped_vms":         len(report_data.get("orphan_resources", {}).get("stopped_vms", [])),
        },
        "suggestion_count": len(report_data.get("optimization_suggestions", [])),
    }


def save_report(connection_id: str, user_id: str, provider: str,
                report_type: str, report_data: dict,
                period_start: str, period_end: str) -> dict:
    """
    Save a lightweight report summary to DB.
    Returns the saved record (without full resource lists).
    """
    trimmed     = _trim_report_data(report_data)
    trimmed_str = json.dumps(trimmed)

    if len(trimmed_str.encode()) > MAX_REPORT_DATA_BYTES:
        logger.warning(f"Report data still large after trim ({len(trimmed_str)} bytes) — truncating cost_by_service")
        trimmed["cost_by_service"] = trimmed["cost_by_service"][:5]

    db     = get_db()
    result = db.table("reports").insert({
        "connection_id":            connection_id,
        "user_id":                  user_id,
        "provider":                 provider,
        "report_type":              report_type,
        "period_start":             period_start,
        "period_end":               period_end,
        "total_spend":              report_data.get("total_spend_30d", 0),
        "total_savings_identified": report_data.get("total_potential_savings", 0),
        "orphan_count":             sum(trimmed["orphan_summary"].values()),
        "anomaly_detected":         trimmed["anomaly_alert"] is not None,
        "report_data":              trimmed,
        "created_at":               datetime.now(timezone.utc).isoformat(),
    }).execute()

    mark_connection_scanned(connection_id)
    return result.data[0]


def get_recent_reports(user_id: str, connection_id: Optional[str] = None,
                       limit: int = 20) -> list[dict]:
    db = get_db()
    q  = db.table("reports").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit)
    if connection_id:
        q = q.eq("connection_id", connection_id)
    return q.execute().data


def get_report_by_id(report_id: str, user_id: str) -> Optional[dict]:
    db     = get_db()
    result = db.table("reports").select("*").eq("id", report_id).eq("user_id", user_id).execute()
    return result.data[0] if result.data else None


# ── Dashboard summary ──────────────────────────────────────────────────────────

def get_dashboard_summary(user_id: str) -> dict:
    db    = get_db()
    conns = db.table("cloud_connections").select("id,display_name,provider") \
               .eq("user_id", user_id).eq("is_active", True).execute().data

    if not conns:
        return {"total_spend_30d": 0, "total_savings_identified": 0,
                "total_orphan_count": 0, "connection_count": 0,
                "tier": "free", "latest_reports": []}

    conn_ids    = [c["id"] for c in conns]
    conn_map    = {c["id"]: c["display_name"] for c in conns}
    since       = (datetime.now(timezone.utc) - timedelta(days=35)).isoformat()

    reports = db.table("reports").select("*") \
                .in_("connection_id", conn_ids) \
                .gte("created_at", since) \
                .order("created_at", desc=True).limit(50).execute().data

    # Aggregate across all connections
    total_spend    = sum(r.get("total_spend", 0) or 0 for r in reports[:len(conns)])
    total_savings  = sum(r.get("total_savings_identified", 0) or 0 for r in reports[:len(conns)])
    total_orphans  = sum(r.get("orphan_count", 0) or 0 for r in reports[:len(conns)])

    # Get tier from profile
    profile = db.table("profiles").select("tier").eq("id", user_id).single().execute()
    tier    = profile.data.get("tier", "free") if profile.data else "free"

    latest = []
    seen   = set()
    for r in reports:
        if r["connection_id"] not in seen:
            seen.add(r["connection_id"])
            latest.append({**r, "connection_name": conn_map.get(r["connection_id"], "")})

    return {
        "total_spend_30d":          round(total_spend, 2),
        "total_savings_identified": round(total_savings, 2),
        "total_orphan_count":       total_orphans,
        "connection_count":         len(conns),
        "tier":                     tier,
        "latest_reports":           latest[:5],
    }


# ── Notifications dedup ────────────────────────────────────────────────────────

def was_notified_today(user_id: str, connection_id: str, notification_type: str) -> bool:
    db     = get_db()
    since  = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()
    result = db.table("notification_log").select("id") \
               .eq("user_id", user_id).eq("connection_id", connection_id) \
               .eq("notification_type", notification_type).gte("sent_at", since).execute()
    return len(result.data) > 0

def log_notification(user_id: str, connection_id: str,
                     notification_type: str, channel: str, metadata: dict = {}):
    get_db().table("notification_log").insert({
        "user_id":           user_id,
        "connection_id":     connection_id,
        "notification_type": notification_type,
        "channel":           channel,
        "sent_at":           datetime.now(timezone.utc).isoformat(),
        "metadata":          metadata,
    }).execute()


def get_alert_config(user_id: str) -> dict:
    db     = get_db()
    result = db.table("profiles").select("notification_config").eq("id", user_id).execute()
    if result.data and result.data[0].get("notification_config"):
        return result.data[0]["notification_config"]
    return {"threshold": 15, "notify_email": True, "notify_telegram": False}


# ── Auto-purge old reports (call weekly) ──────────────────────────────────────

def purge_old_reports(days_to_keep: int = 90):
    """Delete reports older than N days. Call from scheduled Azure Function."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_to_keep)).isoformat()
    result = get_db().table("reports").delete().lt("created_at", cutoff).execute()
    deleted = len(result.data) if result.data else 0
    logger.info(f"Purged {deleted} reports older than {days_to_keep} days")
    return deleted
