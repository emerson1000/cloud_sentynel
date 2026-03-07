"""
CloudSentinel - GCP Cost Analyzer
Uses Google Cloud Python SDK to analyze GCP projects for orphaned resources,
cost anomalies, and optimization opportunities.

Required IAM roles (assign to the CloudSentinel service account):
  - roles/billing.viewer               — read billing data
  - roles/compute.viewer               — read VM/disk/network resources
  - roles/monitoring.viewer            — read Cloud Monitoring metrics
  - roles/recommender.viewer           — read Recommender API suggestions (optional but powerful)

Setup:
  1. Create a Service Account in GCP Console
  2. Assign the roles above
  3. Download the JSON key file
  4. Pass the parsed JSON as service_account_info
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd
from google.oauth2 import service_account
from google.cloud import billing_v1
from google.cloud import compute_v1
from google.cloud import monitoring_v3
from google.cloud.monitoring_v3.types import TimeInterval
from google.protobuf.timestamp_pb2 import Timestamp

from core.base_analyzer import (
    BaseCloudAnalyzer,
    OrphanResource,
    AnomalyAlert,
    OptimizationSuggestion,
)

logger = logging.getLogger(__name__)


class GCPAnalyzer(BaseCloudAnalyzer):
    PROVIDER = "gcp"

    def __init__(
        self,
        service_account_info: dict,
        project_id: str,
        billing_account_id: str,
    ):
        self.project_id = project_id
        self.billing_account_id = billing_account_id  # Format: "XXXXXX-XXXXXX-XXXXXX"

        self._credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )

        self._disks_client = None
        self._addresses_client = None
        self._instances_client = None
        self._forwarding_rules_client = None
        self._monitoring_client = None
        self._billing_client = None

    def _get_account_id(self) -> str:
        return self.project_id

    @property
    def disks_client(self):
        if not self._disks_client:
            self._disks_client = compute_v1.DisksClient(credentials=self._credentials)
        return self._disks_client

    @property
    def addresses_client(self):
        if not self._addresses_client:
            self._addresses_client = compute_v1.AddressesClient(credentials=self._credentials)
        return self._addresses_client

    @property
    def instances_client(self):
        if not self._instances_client:
            self._instances_client = compute_v1.InstancesClient(credentials=self._credentials)
        return self._instances_client

    @property
    def forwarding_rules_client(self):
        if not self._forwarding_rules_client:
            self._forwarding_rules_client = compute_v1.ForwardingRulesClient(credentials=self._credentials)
        return self._forwarding_rules_client

    @property
    def monitoring_client(self):
        if not self._monitoring_client:
            self._monitoring_client = monitoring_v3.MetricServiceClient(credentials=self._credentials)
        return self._monitoring_client

    # ─── COST DATA ────────────────────────────────────────────────────────────
    # NOTE: GCP billing data is typically exported to BigQuery.
    # For the MVP we use the Cloud Billing API budget/cost summary.
    # For production, switch to BigQuery export for richer daily granularity.

    def get_daily_costs(self, days: int = 30) -> pd.DataFrame:
        """
        GCP best practice: export billing data to BigQuery and query it.
        This implementation uses the Cloud Billing API for a simpler MVP approach.
        For full daily/service breakdown, configure BigQuery export in the GCP Console
        and replace this method with a BigQuery client query.
        """
        try:
            from google.cloud import bigquery
            return self._get_daily_costs_bigquery(days)
        except ImportError:
            logger.warning("[GCP] BigQuery client not available — using stub cost data")
            return pd.DataFrame(columns=["date", "service", "cost", "currency"])

    def _get_daily_costs_bigquery(self, days: int) -> pd.DataFrame:
        """
        Requires: billing export to BigQuery enabled, and roles/bigquery.dataViewer.
        In GCP Console: Billing → Billing Export → BigQuery Export.
        The dataset is typically named: billing_export
        Table: gcp_billing_export_v1_<BILLING_ACCOUNT_ID>
        """
        from google.cloud import bigquery

        bq_client = bigquery.Client(
            project=self.project_id,
            credentials=self._credentials
        )

        # Normalize billing account ID for BQ table name: remove dashes
        bq_billing_id = self.billing_account_id.replace("-", "_").upper()
        table = f"`{self.project_id}.billing_export.gcp_billing_export_v1_{bq_billing_id}`"

        query = f"""
        SELECT
          DATE(usage_start_time) AS date,
          service.description AS service,
          SUM(cost + IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS cost,
          currency
        FROM {table}
        WHERE
          project.id = @project_id
          AND DATE(usage_start_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
        GROUP BY date, service, currency
        ORDER BY date DESC
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("project_id", "STRING", self.project_id)
            ]
        )

        df = bq_client.query(query, job_config=job_config).to_dataframe()
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df["cost"] = df["cost"].astype(float)
        return df

    def detect_anomaly(self, threshold_pct: float = 15.0) -> Optional[AnomalyAlert]:
        df = self.get_daily_costs(days=14)
        if df.empty:
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

        yesterday_df = df[df["date"] == yesterday["date"]]
        top_services = (
            yesterday_df.groupby("service")["cost"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
            .reset_index()
            .to_dict("records")
        )

        return AnomalyAlert(
            date=yesterday["date"].strftime("%Y-%m-%d"),
            yesterday_spend=round(yesterday["cost"], 2),
            avg_7day_spend=round(avg_7day, 2),
            delta_pct=round(delta_pct, 1),
            top_services=top_services,
            severity="critical" if abs(delta_pct) > 30 else "warning",
        )

    def get_cost_by_service(self, days: int = 30) -> list[dict]:
        df = self.get_daily_costs(days)
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

    # ─── ZOMBIE RESOURCES ─────────────────────────────────────────────────────

    def find_orphan_disks(self) -> list[OrphanResource]:
        """Persistent Disks not attached to any instance (status=READY, no users)."""
        orphans = []

        # Aggregate disk list across all zones
        agg_request = compute_v1.AggregatedListDisksRequest(project=self.project_id)
        agg_list = self.disks_client.aggregated_list(request=agg_request)

        for zone_name, disks_scoped in agg_list:
            if not disks_scoped.disks:
                continue
            for disk in disks_scoped.disks:
                if disk.status == "READY" and not disk.users:
                    gb = disk.size_gb or 0
                    disk_type = disk.type_.split("/")[-1] if disk.type_ else "pd-standard"

                    # GCP pricing (us-central1 approximate)
                    price_map = {
                        "pd-standard": 0.04,
                        "pd-ssd": 0.17,
                        "pd-balanced": 0.10,
                        "pd-extreme": 0.12,
                        "hyperdisk-balanced": 0.12,
                    }
                    price = price_map.get(disk_type, 0.04)
                    estimated_cost = gb * price

                    zone = zone_name.replace("zones/", "")
                    orphans.append(OrphanResource(
                        resource_id=f"projects/{self.project_id}/zones/{zone}/disks/{disk.name}",
                        name=disk.name,
                        resource_type="Persistent Disk",
                        resource_group=f"{self.project_id}/{zone}",
                        location=zone,
                        estimated_monthly_cost_usd=round(estimated_cost, 2),
                        reason=f"Unattached {disk_type} Persistent Disk ({gb} GB) — not linked to any instance",
                        tags=dict(disk.labels or {}),
                    ))

        return orphans

    def find_orphan_public_ips(self) -> list[OrphanResource]:
        """Static External IPs (RESERVED but not IN_USE)."""
        orphans = []

        # List global addresses
        global_request = compute_v1.ListGlobalAddressesRequest(project=self.project_id)
        for addr in self.addresses_client.list(request=global_request):
            if addr.status == "RESERVED" and not addr.users:
                orphans.append(OrphanResource(
                    resource_id=f"projects/{self.project_id}/global/addresses/{addr.name}",
                    name=addr.name,
                    resource_type="Static External IP (Global)",
                    resource_group=self.project_id,
                    location="global",
                    estimated_monthly_cost_usd=7.20,  # ~$0.01/hr for reserved unused static IP
                    reason=f"Reserved static IP {addr.address} not attached to any resource",
                    tags=dict(addr.labels or {}),
                ))

        # List regional addresses
        from google.cloud.compute_v1 import AggregatedListAddressesRequest
        agg_request = AggregatedListAddressesRequest(project=self.project_id)
        for region_name, addresses_scoped in self.addresses_client.aggregated_list(request=agg_request):
            if not addresses_scoped.addresses:
                continue
            for addr in addresses_scoped.addresses:
                if addr.status == "RESERVED" and not addr.users:
                    region = region_name.replace("regions/", "")
                    orphans.append(OrphanResource(
                        resource_id=f"projects/{self.project_id}/regions/{region}/addresses/{addr.name}",
                        name=addr.name,
                        resource_type="Static External IP (Regional)",
                        resource_group=f"{self.project_id}/{region}",
                        location=region,
                        estimated_monthly_cost_usd=7.20,
                        reason=f"Reserved regional static IP {addr.address} not attached to any resource",
                        tags=dict(addr.labels or {}),
                    ))

        return orphans

    def find_idle_load_balancers(self) -> list[OrphanResource]:
        """Forwarding rules with no healthy backends (Cloud Load Balancing)."""
        orphans = []

        # GCP Load Balancing is complex (HTTP(S) LB uses forwarding rules + backend services)
        # We check forwarding rules with no attached backend service users
        from google.cloud.compute_v1 import AggregatedListForwardingRulesRequest
        agg_request = AggregatedListForwardingRulesRequest(project=self.project_id)

        for region_name, rules_scoped in self.forwarding_rules_client.aggregated_list(request=agg_request):
            if not rules_scoped.forwarding_rules:
                continue
            for rule in rules_scoped.forwarding_rules:
                # Check if the backend service exists and has backends
                if rule.backend_service:
                    try:
                        backend_svc_name = rule.backend_service.split("/")[-1]
                        region = region_name.replace("regions/", "")
                        bs_client = compute_v1.BackendServicesClient(credentials=self._credentials)
                        bs = bs_client.get(project=self.project_id, backend_service=backend_svc_name)
                        if not bs.backends:
                            orphans.append(OrphanResource(
                                resource_id=f"projects/{self.project_id}/regions/{region}/forwardingRules/{rule.name}",
                                name=rule.name,
                                resource_type="Load Balancer Forwarding Rule",
                                resource_group=f"{self.project_id}/{region}",
                                location=region,
                                estimated_monthly_cost_usd=18.0,
                                reason=f"Forwarding rule points to backend service '{backend_svc_name}' which has no backends",
                                tags=dict(rule.labels or {}),
                            ))
                    except Exception as e:
                        logger.debug(f"[GCP] Could not inspect backend service for {rule.name}: {e}")

        return orphans

    def find_stopped_vms_still_paying(self) -> list[OrphanResource]:
        """
        GCP VMs in TERMINATED state.
        Like AWS, compute charges stop when terminated, but attached Persistent Disks
        and reserved IPs continue to be billed.
        """
        orphans = []

        agg_request = compute_v1.AggregatedListInstancesRequest(
            project=self.project_id,
            filter="status=TERMINATED"
        )

        for zone_name, instances_scoped in self.instances_client.aggregated_list(request=agg_request):
            if not instances_scoped.instances:
                continue
            for inst in instances_scoped.instances:
                zone = zone_name.replace("zones/", "")
                # Count attached disks (still charged)
                disk_cost = len(inst.disks or []) * 8  # rough $8/disk estimate

                orphans.append(OrphanResource(
                    resource_id=f"projects/{self.project_id}/zones/{zone}/instances/{inst.name}",
                    name=inst.name,
                    resource_type="Compute Engine Instance",
                    resource_group=f"{self.project_id}/{zone}",
                    location=zone,
                    estimated_monthly_cost_usd=round(disk_cost, 2),
                    reason=f"TERMINATED instance ({inst.machine_type.split('/')[-1]}). "
                           f"No compute charges, but {len(inst.disks or [])} attached disk(s) "
                           f"still billing (~${disk_cost}/mo). Consider deleting if unused.",
                    tags=dict(inst.labels or {}),
                ))

        return orphans

    # ─── OPTIMIZATION SUGGESTIONS ─────────────────────────────────────────────

    def suggest_reserved_instances(self) -> list[OptimizationSuggestion]:
        """
        Use the GCP Recommender API for Committed Use Discount (CUD) recommendations.
        These are GCP's equivalent of AWS Reserved Instances — up to 57% savings.
        Falls back to manual CloudWatch-style check if Recommender API unavailable.
        """
        suggestions = []

        try:
            from google.cloud import recommender_v1
            recommender_client = recommender_v1.RecommenderClient(credentials=self._credentials)

            # GCP Recommender: committed use discounts for Compute Engine
            recommender_id = "google.compute.commitment.UsageCommitmentRecommender"

            # Recommendations are per-region; iterate common regions
            regions = self._get_active_regions()

            for region in regions:
                parent = f"projects/{self.project_id}/locations/{region}/recommenders/{recommender_id}"
                try:
                    for rec in recommender_client.list_recommendations(parent=parent):
                        if rec.state_info.state != recommender_v1.RecommendationStateInfo.State.ACTIVE:
                            continue

                        # Extract impact
                        impact = None
                        for i in rec.primary_impact:
                            if i.category == recommender_v1.Impact.Category.COST:
                                impact = i
                                break

                        if not impact:
                            continue

                        savings = abs(float(impact.cost_projection.cost.units)) + abs(
                            float(impact.cost_projection.cost.nanos) / 1e9
                        )

                        suggestions.append(OptimizationSuggestion(
                            resource_id=rec.name,
                            resource_name=rec.description[:80],
                            suggestion_type="committed_use",
                            current_cost_monthly=round(savings / 0.37, 2),  # est. On-Demand from savings
                            estimated_savings_monthly=round(savings, 2),
                            confidence="high",
                            detail=f"{rec.description} (GCP Recommender API suggestion, region: {region})",
                        ))
                except Exception as e:
                    logger.debug(f"[GCP] Recommender unavailable for {region}: {e}")

        except ImportError:
            logger.warning("[GCP] Recommender API not available, using manual check")
            suggestions.extend(self._manual_cud_suggestions())

        return suggestions

    def _manual_cud_suggestions(self) -> list[OptimizationSuggestion]:
        """Find VMs running consistently via Cloud Monitoring — suggest CUDs."""
        suggestions = []
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=30)

        project_name = f"projects/{self.project_id}"

        start_ts = Timestamp()
        start_ts.FromDatetime(start)
        end_ts = Timestamp()
        end_ts.FromDatetime(end)

        interval = TimeInterval({"start_time": start_ts, "end_time": end_ts})

        # Query CPU utilization per instance
        try:
            results = self.monitoring_client.list_time_series(
                request={
                    "name": project_name,
                    "filter": 'metric.type = "compute.googleapis.com/instance/cpu/utilization"',
                    "interval": interval,
                    "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                }
            )

            instance_uptime = {}
            for ts in results:
                instance_id = ts.resource.labels.get("instance_id", "")
                zone = ts.resource.labels.get("zone", "")
                uptime_days = len(ts.points)
                if uptime_days >= 24:
                    instance_uptime[instance_id] = {"zone": zone, "uptime_days": uptime_days}

            for inst_id, info in list(instance_uptime.items())[:10]:
                zone = info["zone"]
                try:
                    inst = self.instances_client.get(project=self.project_id, zone=zone, instance=inst_id)
                    machine_type = inst.machine_type.split("/")[-1] if inst.machine_type else "unknown"
                    est_monthly = 120.0  # rough On-Demand estimate
                    savings = est_monthly * 0.37  # CUD 1-year ~37% discount

                    suggestions.append(OptimizationSuggestion(
                        resource_id=f"projects/{self.project_id}/zones/{zone}/instances/{inst.name}",
                        resource_name=inst.name,
                        suggestion_type="committed_use",
                        current_cost_monthly=est_monthly,
                        estimated_savings_monthly=round(savings, 2),
                        confidence="medium",
                        detail=f"{machine_type} ran {info['uptime_days']}/30 days. "
                               f"1-year CUD could save ~37% (~${savings:.0f}/mo).",
                    ))
                except Exception as e:
                    logger.debug(f"[GCP] Could not get instance info for {inst_id}: {e}")

        except Exception as e:
            logger.warning(f"[GCP] Manual CUD check failed: {e}")

        return suggestions

    def _get_active_regions(self) -> list[str]:
        """Return list of regions that have active resources."""
        try:
            regions_client = compute_v1.RegionsClient(credentials=self._credentials)
            return [r.name for r in regions_client.list(project=self.project_id)]
        except Exception:
            # Fallback to common regions
            return [
                "us-central1", "us-east1", "us-west1", "us-west2",
                "europe-west1", "europe-west2", "europe-west3",
                "asia-east1", "asia-southeast1", "southamerica-east1",
            ]
