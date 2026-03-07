"""
CloudSentinel - Notification Engine
Sends alerts via Resend (email) and Telegram Bot API.
"""

import os
import json
import logging
import httpx
from datetime import datetime
from jinja2 import Template

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "alerts@cloudsentinel.io")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")


# ─── EMAIL TEMPLATES ──────────────────────────────────────────────────────────

WEEKLY_REPORT_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { font-family: 'Segoe UI', Arial, sans-serif; background: #0d1117; color: #e6edf3; margin: 0; padding: 0; }
    .container { max-width: 640px; margin: 0 auto; padding: 32px 24px; }
    .header { background: linear-gradient(135deg, #1f6feb, #58a6ff); padding: 32px; border-radius: 12px; margin-bottom: 24px; }
    .header h1 { margin: 0; font-size: 24px; color: white; }
    .header p { margin: 8px 0 0; color: rgba(255,255,255,0.8); font-size: 14px; }
    .card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 20px; margin-bottom: 16px; }
    .metric { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #21262d; }
    .metric:last-child { border-bottom: none; }
    .metric-label { color: #8b949e; font-size: 14px; }
    .metric-value { font-size: 18px; font-weight: 600; color: #58a6ff; }
    .metric-value.danger { color: #f85149; }
    .metric-value.success { color: #3fb950; }
    .section-title { font-size: 16px; font-weight: 600; margin: 0 0 12px; color: #e6edf3; }
    .orphan-item { background: #0d1117; border-left: 3px solid #f85149; padding: 12px 16px; margin-bottom: 8px; border-radius: 0 6px 6px 0; }
    .orphan-name { font-weight: 600; font-size: 14px; }
    .orphan-reason { color: #8b949e; font-size: 12px; margin-top: 4px; }
    .orphan-cost { color: #f85149; font-weight: 600; font-size: 14px; float: right; }
    .suggestion-item { background: #0d1117; border-left: 3px solid #3fb950; padding: 12px 16px; margin-bottom: 8px; border-radius: 0 6px 6px 0; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }
    .badge-warning { background: #9e6a03; color: #ffa657; }
    .badge-critical { background: #490202; color: #f85149; }
    .cta { background: #1f6feb; color: white; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600; display: inline-block; margin-top: 16px; }
    .footer { text-align: center; color: #8b949e; font-size: 12px; margin-top: 32px; }
  </style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>☁️ CloudSentinel Weekly Report</h1>
    <p>{{ report_date }} · Subscription: {{ subscription_id[:8] }}...</p>
  </div>

  <div class="card">
    <div class="section-title">💰 Spend Summary (Last 30 days)</div>
    <div class="metric">
      <span class="metric-label">Total Spend</span>
      <span class="metric-value">${{ "%.2f"|format(total_spend) }}</span>
    </div>
    <div class="metric">
      <span class="metric-label">Potential Monthly Savings Identified</span>
      <span class="metric-value success">${{ "%.2f"|format(total_savings) }}</span>
    </div>
    <div class="metric">
      <span class="metric-label">Zombie Resources Found</span>
      <span class="metric-value {% if orphan_count > 0 %}danger{% endif %}">{{ orphan_count }}</span>
    </div>
    {% if anomaly %}
    <div class="metric">
      <span class="metric-label">Anomaly Detected</span>
      <span class="badge badge-{{ anomaly.severity }}">↑{{ anomaly.delta_pct }}% vs 7-day avg</span>
    </div>
    {% endif %}
  </div>

  {% if orphans %}
  <div class="card">
    <div class="section-title">🧟 Zombie Resources (Stop Paying for These)</div>
    {% for r in orphans %}
    <div class="orphan-item">
      <span class="orphan-cost">${{ "%.2f"|format(r.estimated_monthly_cost_usd) }}/mo</span>
      <div class="orphan-name">{{ r.name }}</div>
      <div class="orphan-reason">{{ r.reason }}</div>
    </div>
    {% endfor %}
  </div>
  {% endif %}

  {% if suggestions %}
  <div class="card">
    <div class="section-title">💡 Optimization Suggestions</div>
    {% for s in suggestions %}
    <div class="suggestion-item">
      <strong>{{ s.resource_name }}</strong> — {{ s.suggestion_type | replace("_", " ") | title }}<br>
      <small style="color:#8b949e">{{ s.detail }}</small><br>
      <span style="color:#3fb950; font-weight:600">Save ~${{ "%.2f"|format(s.estimated_savings_monthly) }}/mo</span>
      <span style="color:#8b949e; font-size:12px"> ({{ s.confidence }} confidence)</span>
    </div>
    {% endfor %}
  </div>
  {% endif %}

  <div style="text-align:center">
    <a href="{{ dashboard_url }}" class="cta">View Full Dashboard →</a>
  </div>

  <div class="footer">
    <p>CloudSentinel · You're on the {{ tier | upper }} plan · <a href="{{ unsubscribe_url }}" style="color:#8b949e">Unsubscribe</a></p>
  </div>
</div>
</body>
</html>
"""

ANOMALY_ALERT_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { font-family: 'Segoe UI', Arial, sans-serif; background: #0d1117; color: #e6edf3; margin: 0; padding: 24px; }
    .alert-box { max-width: 560px; margin: 0 auto; background: #1a0000; border: 1px solid #f85149; border-radius: 12px; padding: 28px; }
    h2 { color: #f85149; margin-top: 0; }
    .number { font-size: 32px; font-weight: 700; color: #f85149; }
    .services { margin-top: 16px; }
    .service-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #21262d; font-size: 14px; }
    .cta { background: #f85149; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; display: inline-block; margin-top: 20px; }
  </style>
</head>
<body>
<div class="alert-box">
  <h2>⚠️ Spending Anomaly Detected</h2>
  <p>Yesterday's spend on <strong>{{ subscription_id[:8] }}...</strong> spiked significantly:</p>
  <div class="number">+{{ anomaly.delta_pct }}%</div>
  <p>vs your 7-day average of <strong>${{ "%.2f"|format(anomaly.avg_7day_spend) }}/day</strong></p>
  <p>Yesterday you spent: <strong>${{ "%.2f"|format(anomaly.yesterday_spend) }}</strong></p>

  {% if anomaly.top_services %}
  <div class="services">
    <strong>Top Services Yesterday:</strong>
    {% for svc in anomaly.top_services %}
    <div class="service-row">
      <span>{{ svc.service }}</span>
      <span>${{ "%.2f"|format(svc.cost) }}</span>
    </div>
    {% endfor %}
  </div>
  {% endif %}

  <a href="{{ dashboard_url }}" class="cta">Investigate Now →</a>
</div>
</body>
</html>
"""


# ─── EMAIL SENDER (Resend) ────────────────────────────────────────────────────

async def send_email(to: str, subject: str, html: str):
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set, skipping email")
        return

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            json={"from": RESEND_FROM_EMAIL, "to": [to], "subject": subject, "html": html},
            timeout=15
        )
        if resp.status_code not in (200, 201):
            logger.error(f"Resend API error {resp.status_code}: {resp.text}")
        else:
            logger.info(f"Email sent to {to}: {subject}")


# ─── TELEGRAM SENDER ─────────────────────────────────────────────────────────

async def send_telegram(chat_id: str, message: str):
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set, skipping Telegram")
        return

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
            timeout=10
        )
        if resp.status_code != 200:
            logger.error(f"Telegram API error {resp.status_code}: {resp.text}")
        else:
            logger.info(f"Telegram message sent to {chat_id}")


# ─── NOTIFICATION BUILDERS ────────────────────────────────────────────────────

def build_telegram_anomaly_message(anomaly: dict, subscription_id: str) -> str:
    emoji = "🚨" if anomaly["severity"] == "critical" else "⚠️"
    top = "\n".join(
        f"  • {s['service']}: ${s['cost']:.2f}" for s in anomaly["top_services"][:3]
    )
    return (
        f"{emoji} *CloudSentinel Alert*\n\n"
        f"Subscription `{subscription_id[:12]}...` spending spike detected!\n\n"
        f"📈 *+{anomaly['delta_pct']}%* vs 7-day average\n"
        f"Yesterday: *${anomaly['yesterday_spend']:.2f}*\n"
        f"Avg: ${anomaly['avg_7day_spend']:.2f}/day\n\n"
        f"*Top services:*\n{top}\n\n"
        f"[View Dashboard](https://app.cloudsentinel.io/dashboard)"
    )


def build_telegram_weekly_summary(report: dict) -> str:
    orphan_count = sum(
        len(v) for v in report.get("orphan_resources", {}).values()
    )
    return (
        f"📊 *CloudSentinel Weekly Report*\n\n"
        f"💰 30-day spend: *${report.get('total_spend_30d', 0):.2f}*\n"
        f"🧟 Zombie resources: *{orphan_count}*\n"
        f"💡 Savings identified: *${report.get('total_potential_savings', 0):.2f}/mo*\n\n"
        f"[View Full Report](https://app.cloudsentinel.io/dashboard)"
    )


async def send_anomaly_notifications(
    email: str,
    anomaly: dict,
    subscription_id: str,
    alert_config: dict,
    tier: str = "free"
):
    if alert_config.get("notify_email"):
        tmpl = Template(ANOMALY_ALERT_HTML)
        html = tmpl.render(
            anomaly=anomaly,
            subscription_id=subscription_id,
            dashboard_url="https://app.cloudsentinel.io/dashboard"
        )
        severity_label = "🚨 Critical" if anomaly["severity"] == "critical" else "⚠️ Warning"
        await send_email(email, f"{severity_label}: Cloud spend anomaly detected (+{anomaly['delta_pct']}%)", html)

    if alert_config.get("notify_telegram") and alert_config.get("telegram_chat_id"):
        msg = build_telegram_anomaly_message(anomaly, subscription_id)
        await send_telegram(alert_config["telegram_chat_id"], msg)


async def send_weekly_report(
    email: str,
    report: dict,
    alert_config: dict,
    tier: str = "free"
):
    if alert_config.get("notify_email"):
        all_orphans = []
        for category in report.get("orphan_resources", {}).values():
            all_orphans.extend(category)

        tmpl = Template(WEEKLY_REPORT_HTML)
        html = tmpl.render(
            report_date=datetime.now().strftime("%B %d, %Y"),
            subscription_id=report.get("subscription_id", ""),
            total_spend=report.get("total_spend_30d", 0),
            total_savings=report.get("total_potential_savings", 0),
            orphan_count=len(all_orphans),
            orphans=all_orphans[:10],  # cap at 10 in email
            suggestions=report.get("optimization_suggestions", [])[:5],
            anomaly=report.get("anomaly_alert"),
            tier=tier,
            dashboard_url="https://app.cloudsentinel.io/dashboard",
            unsubscribe_url="https://app.cloudsentinel.io/settings/notifications"
        )
        await send_email(email, f"☁️ Your Weekly Cloud Cost Report — ${report.get('total_spend_30d', 0):.2f} spent", html)

    if alert_config.get("notify_telegram") and alert_config.get("telegram_chat_id"):
        msg = build_telegram_weekly_summary(report)
        await send_telegram(alert_config["telegram_chat_id"], msg)
