"""
CloudSentinel - Base Cloud Analyzer
Abstract interface that ALL cloud providers must implement.
This ensures AzureAnalyzer, AWSAnalyzer, and GCPAnalyzer are
interchangeable — the rest of the system (functions, API) never
needs to know which provider it's talking to.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)


# ─── SHARED DATA MODELS (provider-agnostic) ───────────────────────────────────

@dataclass
class OrphanResource:
    resource_id: str
    name: str
    resource_type: str        # e.g. "EBS Volume", "Managed Disk", "Persistent Disk"
    resource_group: str       # AWS: account/region, GCP: project/region, Azure: resource group
    location: str
    estimated_monthly_cost_usd: float
    reason: str
    tags: dict


@dataclass
class AnomalyAlert:
    date: str
    yesterday_spend: float
    avg_7day_spend: float
    delta_pct: float
    top_services: list
    severity: str             # "warning" | "critical"


@dataclass
class OptimizationSuggestion:
    resource_id: str
    resource_name: str
    suggestion_type: str      # "reserved_instance" | "rightsize" | "delete" | "shutdown_schedule" | "committed_use"
    current_cost_monthly: float
    estimated_savings_monthly: float
    confidence: str           # "high" | "medium" | "low"
    detail: str


@dataclass
class FullReport:
    provider: str             # "azure" | "aws" | "gcp"
    account_id: str           # subscription_id / account_id / project_id
    generated_at: str
    period_days: int
    total_spend_30d: float
    cost_by_service: list
    anomaly_alert: Optional[dict]
    orphan_resources: dict
    total_orphan_savings: float
    optimization_suggestions: list
    total_potential_savings: float

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ─── ABSTRACT BASE ────────────────────────────────────────────────────────────

class BaseCloudAnalyzer(ABC):
    """
    Every cloud provider analyzer must implement these methods.
    The constructor signature is provider-specific, but generate_full_report()
    always returns a FullReport — that's the contract.
    """

    PROVIDER: str = "unknown"

    @abstractmethod
    def get_daily_costs(self, days: int = 30):
        """
        Returns a pandas DataFrame with columns:
          date (datetime), service (str), cost (float), currency (str)
        """
        ...

    @abstractmethod
    def detect_anomaly(self, threshold_pct: float = 15.0) -> Optional[AnomalyAlert]:
        """Compare yesterday's spend vs 7-day average. Return AnomalyAlert if threshold exceeded."""
        ...

    @abstractmethod
    def find_orphan_disks(self) -> list[OrphanResource]:
        """Find unattached block storage volumes."""
        ...

    @abstractmethod
    def find_orphan_public_ips(self) -> list[OrphanResource]:
        """Find public IPs/Elastic IPs not associated with any resource."""
        ...

    @abstractmethod
    def find_idle_load_balancers(self) -> list[OrphanResource]:
        """Find load balancers with no active backend targets."""
        ...

    @abstractmethod
    def find_stopped_vms_still_paying(self) -> list[OrphanResource]:
        """Find compute instances stopped but still incurring charges."""
        ...

    @abstractmethod
    def suggest_reserved_instances(self) -> list[OptimizationSuggestion]:
        """Identify long-running instances that would benefit from reserved/committed pricing."""
        ...

    @abstractmethod
    def get_cost_by_service(self, days: int = 30) -> list[dict]:
        """Return cost breakdown by service, sorted descending."""
        ...

    # ── Shared logic (no override needed) ─────────────────────────────────────

    def get_all_orphans(self) -> dict:
        logger.info(f"[{self.PROVIDER}] Scanning for orphaned resources...")
        return {
            "unattached_disks":    [asdict(r) for r in self.find_orphan_disks()],
            "idle_public_ips":     [asdict(r) for r in self.find_orphan_public_ips()],
            "idle_load_balancers": [asdict(r) for r in self.find_idle_load_balancers()],
            "stopped_vms":         [asdict(r) for r in self.find_stopped_vms_still_paying()],
        }

    def generate_full_report(self) -> dict:
        logger.info(f"[{self.PROVIDER}] Generating full report...")
        report = FullReport(
            provider=self.PROVIDER,
            account_id=self._get_account_id(),
            generated_at=datetime.now(timezone.utc).isoformat(),
            period_days=30,
            total_spend_30d=0,
            cost_by_service=[],
            anomaly_alert=None,
            orphan_resources={},
            total_orphan_savings=0,
            optimization_suggestions=[],
            total_potential_savings=0,
        )

        try:
            df = self.get_daily_costs(30)
            report.total_spend_30d = round(float(df["cost"].sum()), 2) if not df.empty else 0
            report.cost_by_service = self.get_cost_by_service(30)
        except Exception as e:
            logger.error(f"[{self.PROVIDER}] Cost analysis failed: {e}")

        try:
            anomaly = self.detect_anomaly()
            report.anomaly_alert = asdict(anomaly) if anomaly else None
        except Exception as e:
            logger.error(f"[{self.PROVIDER}] Anomaly detection failed: {e}")

        try:
            report.orphan_resources = self.get_all_orphans()
            all_orphans = [r for cat in report.orphan_resources.values() for r in cat]
            report.total_orphan_savings = round(
                sum(r["estimated_monthly_cost_usd"] for r in all_orphans), 2
            )
        except Exception as e:
            logger.error(f"[{self.PROVIDER}] Orphan scan failed: {e}")

        try:
            suggestions = self.suggest_reserved_instances()
            report.optimization_suggestions = [asdict(s) for s in suggestions]
            report.total_potential_savings = round(
                sum(s.estimated_savings_monthly for s in suggestions) + report.total_orphan_savings, 2
            )
        except Exception as e:
            logger.error(f"[{self.PROVIDER}] Optimization suggestions failed: {e}")

        return report.to_dict()

    @abstractmethod
    def _get_account_id(self) -> str:
        """Return the account/subscription/project identifier."""
        ...


# ─── FACTORY ─────────────────────────────────────────────────────────────────

def create_analyzer(provider: str, credentials: dict) -> BaseCloudAnalyzer:
    """
    Factory function — instantiates the right analyzer from a connection record.

    credentials for Azure:
        tenant_id, client_id, client_secret, subscription_id
    credentials for AWS:
        aws_access_key_id, aws_secret_access_key, aws_region, account_id
    credentials for GCP:
        service_account_json (dict), project_id, billing_account_id
    """
    if provider == "azure":
        from core.azure_analyzer import AzureAnalyzer
        return AzureAnalyzer(
            tenant_id=credentials["tenant_id"],
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
            subscription_id=credentials["subscription_id"],
        )
    elif provider == "aws":
        from core.aws_analyzer import AWSAnalyzer
        return AWSAnalyzer(
            aws_access_key_id=credentials["aws_access_key_id"],
            aws_secret_access_key=credentials["aws_secret_access_key"],
            region=credentials.get("aws_region", "us-east-1"),
            account_id=credentials["account_id"],
        )
    elif provider == "gcp":
        from core.gcp_analyzer import GCPAnalyzer
        return GCPAnalyzer(
            service_account_info=credentials["service_account_json"],
            project_id=credentials["project_id"],
            billing_account_id=credentials["billing_account_id"],
        )
    else:
        raise ValueError(f"Unknown provider: {provider}. Must be 'azure', 'aws', or 'gcp'.")
