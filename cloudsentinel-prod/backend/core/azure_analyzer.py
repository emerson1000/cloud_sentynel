"""
CloudSentinel - Azure Cost Analyzer Core
Handles all Azure SDK interactions and cost analysis logic.
"""

import os
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from dataclasses import dataclass, asdict

from azure.identity import ClientSecretCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.monitor import MonitorManagementClient
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class OrphanResource:
    resource_id: str
    name: str
    resource_type: str
    resource_group: str
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
    severity: str  # "warning" | "critical"


@dataclass
class OptimizationSuggestion:
    resource_id: str
    resource_name: str
    suggestion_type: str  # "reserved_instance" | "rightsize" | "delete" | "shutdown_schedule"
    current_cost_monthly: float
    estimated_savings_monthly: float
    confidence: str  # "high" | "medium" | "low"
    detail: str


class AzureAnalyzer:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str, subscription_id: str):
        self.subscription_id = subscription_id
        self.credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        self._cost_client = None
        self._resource_client = None
        self._compute_client = None
        self._network_client = None
        self._monitor_client = None

    @property
    def cost_client(self):
        if not self._cost_client:
            self._cost_client = CostManagementClient(self.credential)
        return self._cost_client

    @property
    def resource_client(self):
        if not self._resource_client:
            self._resource_client = ResourceManagementClient(self.credential, self.subscription_id)
        return self._resource_client

    @property
    def compute_client(self):
        if not self._compute_client:
            self._compute_client = ComputeManagementClient(self.credential, self.subscription_id)
        return self._compute_client

    @property
    def network_client(self):
        if not self._network_client:
            self._network_client = NetworkManagementClient(self.credential, self.subscription_id)
        return self._network_client

    @property
    def monitor_client(self):
        if not self._monitor_client:
            self._monitor_client = MonitorManagementClient(self.credential, self.subscription_id)
        return self._monitor_client

    # ─── COST DATA ────────────────────────────────────────────────────────────

    def get_daily_costs(self, days: int = 30) -> pd.DataFrame:
        """Fetch daily cost breakdown for the last N days."""
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days)

        scope = f"/subscriptions/{self.subscription_id}"
        query_body = {
            "type": "ActualCost",
            "timeframe": "Custom",
            "timePeriod": {
                "from": start_date.strftime("%Y-%m-%dT00:00:00Z"),
                "to": end_date.strftime("%Y-%m-%dT23:59:59Z")
            },
            "dataset": {
                "granularity": "Daily",
                "aggregation": {
                    "totalCost": {"name": "Cost", "function": "Sum"}
                },
                "grouping": [
                    {"type": "Dimension", "name": "ServiceName"},
                    {"type": "Dimension", "name": "ResourceGroup"}
                ]
            }
        }

        result = self.cost_client.query.usage(scope=scope, parameters=query_body)
        rows = []
        if result.rows:
            for row in result.rows:
                rows.append({
                    "cost": float(row[0]),
                    "date": str(row[1]),
                    "service": str(row[2]),
                    "resource_group": str(row[3]),
                    "currency": str(row[4]) if len(row) > 4 else "USD"
                })

        df = pd.DataFrame(rows)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
        return df

    def detect_anomaly(self, threshold_pct: float = 15.0) -> Optional[AnomalyAlert]:
        """Compare yesterday's spend vs. 7-day average. Return alert if threshold exceeded."""
        df = self.get_daily_costs(days=14)
        if df.empty:
            logger.warning("No cost data available for anomaly detection")
            return None

        daily_totals = df.groupby("date")["cost"].sum().reset_index().sort_values("date")

        if len(daily_totals) < 2:
            return None

        yesterday = daily_totals.iloc[-1]
        last_7 = daily_totals.iloc[-8:-1] if len(daily_totals) >= 8 else daily_totals.iloc[:-1]
        avg_7day = last_7["cost"].mean()

        if avg_7day == 0:
            return None

        delta_pct = ((yesterday["cost"] - avg_7day) / avg_7day) * 100

        if abs(delta_pct) < threshold_pct:
            return None

        # Top services driving the cost
        yesterday_df = df[df["date"] == yesterday["date"]]
        top_services = (
            yesterday_df.groupby("service")["cost"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
            .reset_index()
            .to_dict("records")
        )

        severity = "critical" if abs(delta_pct) > 30 else "warning"

        return AnomalyAlert(
            date=yesterday["date"].strftime("%Y-%m-%d"),
            yesterday_spend=round(yesterday["cost"], 2),
            avg_7day_spend=round(avg_7day, 2),
            delta_pct=round(delta_pct, 1),
            top_services=top_services,
            severity=severity
        )

    # ─── ZOMBIE RESOURCES ─────────────────────────────────────────────────────

    def find_orphan_disks(self) -> list[OrphanResource]:
        """Find Managed Disks not attached to any VM."""
        orphans = []
        disks = self.compute_client.disks.list()

        for disk in disks:
            if disk.disk_state in ("Unattached", None) and not disk.managed_by:
                # Rough cost estimate: ~$0.04/GB/month for Standard, ~$0.10/GB/month for Premium
                gb = disk.disk_size_gb or 0
                sku = (disk.sku.name or "").lower()
                price_per_gb = 0.10 if "premium" in sku else 0.04
                estimated_cost = gb * price_per_gb

                orphans.append(OrphanResource(
                    resource_id=disk.id,
                    name=disk.name,
                    resource_type="Microsoft.Compute/disks",
                    resource_group=disk.id.split("/")[4],
                    location=disk.location,
                    estimated_monthly_cost_usd=round(estimated_cost, 2),
                    reason=f"Unattached {sku or 'Standard'} disk ({gb} GB) with no VM association",
                    tags=dict(disk.tags or {})
                ))

        return orphans

    def find_orphan_public_ips(self) -> list[OrphanResource]:
        """Find Public IP addresses not associated with any resource."""
        orphans = []
        public_ips = self.network_client.public_ip_addresses.list_all()

        for ip in public_ips:
            is_unassociated = (
                ip.ip_configuration is None and
                ip.nat_gateway is None
            )
            if is_unassociated:
                # Static IPs ~$3.65/month, Dynamic free when unassigned but billed when reserved
                sku_name = ip.sku.name if ip.sku else "Basic"
                estimated_cost = 3.65 if ip.public_ip_allocation_method == "Static" else 0.004 * 730

                orphans.append(OrphanResource(
                    resource_id=ip.id,
                    name=ip.name,
                    resource_type="Microsoft.Network/publicIPAddresses",
                    resource_group=ip.id.split("/")[4],
                    location=ip.location,
                    estimated_monthly_cost_usd=round(estimated_cost, 2),
                    reason=f"{ip.public_ip_allocation_method} Public IP ({sku_name} SKU) not attached to any resource",
                    tags=dict(ip.tags or {})
                ))

        return orphans

    def find_idle_load_balancers(self) -> list[OrphanResource]:
        """Find Load Balancers with no backend pool members."""
        orphans = []
        lbs = self.network_client.load_balancers.list_all()

        for lb in lbs:
            has_backends = False
            if lb.backend_address_pools:
                for pool in lb.backend_address_pools:
                    if pool.backend_ip_configurations or pool.load_balancer_backend_addresses:
                        has_backends = True
                        break

            if not has_backends:
                # Standard LB ~$18/month base cost
                orphans.append(OrphanResource(
                    resource_id=lb.id,
                    name=lb.name,
                    resource_type="Microsoft.Network/loadBalancers",
                    resource_group=lb.id.split("/")[4],
                    location=lb.location,
                    estimated_monthly_cost_usd=18.0,
                    reason="Load Balancer has no backend pool members (idle resource)",
                    tags=dict(lb.tags or {})
                ))

        return orphans

    def find_stopped_vms_still_paying(self) -> list[OrphanResource]:
        """Find VMs in 'Stopped' (not Deallocated) state — still billed!"""
        orphans = []
        vms = self.compute_client.virtual_machines.list_all()

        for vm in vms:
            try:
                instance_view = self.compute_client.virtual_machines.instance_view(
                    vm.id.split("/")[4], vm.name
                )
                statuses = [s.code for s in (instance_view.statuses or [])]
                if "PowerState/stopped" in statuses:
                    orphans.append(OrphanResource(
                        resource_id=vm.id,
                        name=vm.name,
                        resource_type="Microsoft.Compute/virtualMachines",
                        resource_group=vm.id.split("/")[4],
                        location=vm.location,
                        estimated_monthly_cost_usd=0.0,  # varies by size
                        reason="VM is Stopped but NOT Deallocated — compute charges still apply! Deallocate to stop billing.",
                        tags=dict(vm.tags or {})
                    ))
            except Exception as e:
                logger.warning(f"Could not get instance view for {vm.name}: {e}")

        return orphans

    def get_all_orphans(self) -> dict:
        """Collect all orphaned/zombie resources."""
        logger.info("Scanning for orphaned resources...")
        return {
            "unattached_disks": [asdict(r) for r in self.find_orphan_disks()],
            "idle_public_ips": [asdict(r) for r in self.find_orphan_public_ips()],
            "idle_load_balancers": [asdict(r) for r in self.find_idle_load_balancers()],
            "stopped_vms": [asdict(r) for r in self.find_stopped_vms_still_paying()],
        }

    # ─── OPTIMIZATION SUGGESTIONS ─────────────────────────────────────────────

    def suggest_reserved_instances(self) -> list[OptimizationSuggestion]:
        """Find VMs running >80% of the month — candidates for Reserved Instances (up to 72% savings)."""
        suggestions = []

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=30)

        vms = list(self.compute_client.virtual_machines.list_all())

        for vm in vms:
            try:
                rg = vm.id.split("/")[4]
                metrics = self.monitor_client.metrics.list(
                    resource_uri=vm.id,
                    timespan=f"{start_time.isoformat()}/{end_time.isoformat()}",
                    interval="P1D",
                    metricnames="Percentage CPU",
                    aggregation="Average"
                )

                if not metrics.value:
                    continue

                daily_values = []
                for metric in metrics.value:
                    for ts in metric.timeseries:
                        for dp in ts.data:
                            if dp.average is not None:
                                daily_values.append(dp.average)

                if not daily_values:
                    continue

                uptime_days = len(daily_values)
                if uptime_days >= 24:  # Ran for at least 24 of 30 days = 80%
                    vm_size = vm.hardware_profile.vm_size if vm.hardware_profile else "Unknown"
                    # Rough pay-as-you-go estimate (varies heavily by size/region)
                    payg_estimate = 150.0  # placeholder; real impl queries Azure retail prices API
                    savings_estimate = payg_estimate * 0.40  # ~40% savings for 1-year RI

                    suggestions.append(OptimizationSuggestion(
                        resource_id=vm.id,
                        resource_name=vm.name,
                        suggestion_type="reserved_instance",
                        current_cost_monthly=payg_estimate,
                        estimated_savings_monthly=round(savings_estimate, 2),
                        confidence="high" if uptime_days >= 28 else "medium",
                        detail=f"VM '{vm.name}' ({vm_size}) ran {uptime_days}/30 days. "
                               f"1-year Reserved Instance could save ~40% (~${savings_estimate:.0f}/mo)."
                    ))
            except Exception as e:
                logger.warning(f"Could not analyze VM {vm.name}: {e}")

        return suggestions

    def get_cost_by_service(self, days: int = 30) -> list[dict]:
        """Return cost breakdown by service for the last N days."""
        df = self.get_daily_costs(days=days)
        if df.empty:
            return []

        breakdown = (
            df.groupby("service")["cost"]
            .sum()
            .sort_values(ascending=False)
            .reset_index()
            .rename(columns={"cost": "total_cost"})
        )
        breakdown["total_cost"] = breakdown["total_cost"].round(2)
        total = breakdown["total_cost"].sum()
        breakdown["percentage"] = (breakdown["total_cost"] / total * 100).round(1)
        return breakdown.to_dict("records")

    def generate_full_report(self) -> dict:
        """Master method: runs all analyses and returns structured report."""
        logger.info(f"Generating full report for subscription {self.subscription_id}")

        report = {
            "subscription_id": self.subscription_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period_days": 30,
        }

        try:
            cost_df = self.get_daily_costs(30)
            report["total_spend_30d"] = round(cost_df["cost"].sum(), 2) if not cost_df.empty else 0
            report["cost_by_service"] = self.get_cost_by_service(30)
        except Exception as e:
            logger.error(f"Cost analysis failed: {e}")
            report["cost_by_service"] = []
            report["total_spend_30d"] = 0

        try:
            anomaly = self.detect_anomaly()
            report["anomaly_alert"] = asdict(anomaly) if anomaly else None
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            report["anomaly_alert"] = None

        try:
            report["orphan_resources"] = self.get_all_orphans()
            all_orphans = []
            for category in report["orphan_resources"].values():
                all_orphans.extend(category)
            report["total_orphan_savings"] = round(
                sum(r["estimated_monthly_cost_usd"] for r in all_orphans), 2
            )
        except Exception as e:
            logger.error(f"Orphan scan failed: {e}")
            report["orphan_resources"] = {}
            report["total_orphan_savings"] = 0

        try:
            suggestions = self.suggest_reserved_instances()
            report["optimization_suggestions"] = [asdict(s) for s in suggestions]
            report["total_potential_savings"] = round(
                sum(s.estimated_savings_monthly for s in suggestions), 2
            ) + report.get("total_orphan_savings", 0)
        except Exception as e:
            logger.error(f"Optimization suggestions failed: {e}")
            report["optimization_suggestions"] = []
            report["total_potential_savings"] = report.get("total_orphan_savings", 0)

        return report
