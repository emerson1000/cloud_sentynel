"""
CloudSentinel - AWS Cost Analyzer
Uses boto3 to analyze AWS accounts for orphaned resources,
cost anomalies, and optimization opportunities.

Required IAM permissions (attach to the CloudSentinel IAM user/role):
  - ce:GetCostAndUsage
  - ce:GetCostForecast
  - ec2:DescribeVolumes
  - ec2:DescribeAddresses
  - ec2:DescribeInstances
  - ec2:DescribeInstanceStatus
  - elasticloadbalancing:DescribeLoadBalancers
  - elasticloadbalancing:DescribeTargetGroups
  - elasticloadbalancing:DescribeTargetHealth
  - cloudwatch:GetMetricStatistics
  - rds:DescribeDBInstances
  - rds:DescribeDBClusters
  - s3:ListBuckets
  - s3:GetBucketLocation

Recommended: Create a dedicated IAM user with only these permissions.
NEVER use root credentials.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import boto3
import pandas as pd
from botocore.exceptions import ClientError

from core.base_analyzer import (
    BaseCloudAnalyzer,
    OrphanResource,
    AnomalyAlert,
    OptimizationSuggestion,
)

logger = logging.getLogger(__name__)


class AWSAnalyzer(BaseCloudAnalyzer):
    PROVIDER = "aws"

    def __init__(
        self,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        region: str = "us-east-1",
        account_id: str = "",
    ):
        self.region = region
        self.account_id = account_id
        self._session = boto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region,
        )
        self._ce = None       # Cost Explorer
        self._ec2 = None
        self._elb = None
        self._cw = None       # CloudWatch
        self._rds = None

    def _get_account_id(self) -> str:
        if not self.account_id:
            try:
                sts = self._session.client("sts")
                self.account_id = sts.get_caller_identity()["Account"]
            except Exception:
                pass
        return self.account_id

    @property
    def ce(self):
        if not self._ce:
            # Cost Explorer is global — always us-east-1
            self._ce = self._session.client("ce", region_name="us-east-1")
        return self._ce

    @property
    def ec2(self):
        if not self._ec2:
            self._ec2 = self._session.client("ec2")
        return self._ec2

    @property
    def elb(self):
        if not self._elb:
            self._elb = self._session.client("elbv2")
        return self._elb

    @property
    def cw(self):
        if not self._cw:
            self._cw = self._session.client("cloudwatch")
        return self._cw

    @property
    def rds(self):
        if not self._rds:
            self._rds = self._session.client("rds")
        return self._rds

    # ─── COST DATA ────────────────────────────────────────────────────────────

    def get_daily_costs(self, days: int = 30) -> pd.DataFrame:
        """Fetch daily costs via AWS Cost Explorer."""
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=days)

        response = self.ce.get_cost_and_usage(
            TimePeriod={
                "Start": start.strftime("%Y-%m-%d"),
                "End": end.strftime("%Y-%m-%d"),
            },
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        rows = []
        for result in response.get("ResultsByTime", []):
            date_str = result["TimePeriod"]["Start"]
            for group in result.get("Groups", []):
                service = group["Keys"][0]
                cost = float(group["Metrics"]["UnblendedCost"]["Amount"])
                currency = group["Metrics"]["UnblendedCost"]["Unit"]
                rows.append({"date": date_str, "service": service, "cost": cost, "currency": currency})

        df = pd.DataFrame(rows)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
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
        """EBS volumes in 'available' state (not attached to any instance)."""
        orphans = []
        paginator = self.ec2.get_paginator("describe_volumes")

        for page in paginator.paginate(Filters=[{"Name": "status", "Values": ["available"]}]):
            for vol in page["Volumes"]:
                gb = vol.get("Size", 0)
                vol_type = vol.get("VolumeType", "gp2")

                # Approx pricing per GB/month (varies by region, these are us-east-1)
                price_map = {
                    "gp2": 0.10, "gp3": 0.08,
                    "io1": 0.125, "io2": 0.125,
                    "st1": 0.045, "sc1": 0.025,
                    "standard": 0.05,
                }
                price = price_map.get(vol_type, 0.10)
                estimated_cost = gb * price

                days_unattached = 0
                if vol.get("CreateTime"):
                    days_unattached = (datetime.now(timezone.utc) - vol["CreateTime"]).days

                orphans.append(OrphanResource(
                    resource_id=vol["VolumeId"],
                    name=vol.get("Tags") and next((t["Value"] for t in vol["Tags"] if t["Key"] == "Name"), vol["VolumeId"]) or vol["VolumeId"],
                    resource_type="EBS Volume",
                    resource_group=f"{self.account_id}/{self.region}",
                    location=vol.get("AvailabilityZone", self.region),
                    estimated_monthly_cost_usd=round(estimated_cost, 2),
                    reason=f"Unattached {vol_type.upper()} EBS volume ({gb} GB), unattached for {days_unattached} days",
                    tags={t["Key"]: t["Value"] for t in vol.get("Tags") or []},
                ))

        return orphans

    def find_orphan_public_ips(self) -> list[OrphanResource]:
        """Elastic IPs not associated with any instance or ENI."""
        orphans = []
        response = self.ec2.describe_addresses()

        for addr in response.get("Addresses", []):
            # Elastic IPs not associated cost ~$3.65/month
            if not addr.get("AssociationId") and not addr.get("InstanceId"):
                name = next(
                    (t["Value"] for t in addr.get("Tags", []) if t["Key"] == "Name"),
                    addr.get("PublicIp", "")
                )
                orphans.append(OrphanResource(
                    resource_id=addr["AllocationId"],
                    name=name,
                    resource_type="Elastic IP",
                    resource_group=f"{self.account_id}/{self.region}",
                    location=self.region,
                    estimated_monthly_cost_usd=3.65,
                    reason=f"Elastic IP {addr.get('PublicIp')} not associated with any instance or ENI",
                    tags={t["Key"]: t["Value"] for t in addr.get("Tags", [])},
                ))

        return orphans

    def find_idle_load_balancers(self) -> list[OrphanResource]:
        """ALB/NLB with no registered targets in any target group."""
        orphans = []

        try:
            lbs = self.elb.describe_load_balancers().get("LoadBalancers", [])
        except ClientError as e:
            logger.warning(f"[AWS] Could not list load balancers: {e}")
            return []

        for lb in lbs:
            lb_arn = lb["LoadBalancerArn"]
            lb_name = lb["LoadBalancerName"]
            lb_type = lb.get("Type", "application")

            # Get target groups for this LB
            tg_response = self.elb.describe_target_groups(LoadBalancerArn=lb_arn)
            target_groups = tg_response.get("TargetGroups", [])

            has_healthy_targets = False
            for tg in target_groups:
                health = self.elb.describe_target_health(TargetGroupArn=tg["TargetGroupArn"])
                if any(
                    t["TargetHealth"]["State"] in ("healthy", "initial")
                    for t in health.get("TargetHealthDescriptions", [])
                ):
                    has_healthy_targets = True
                    break

            if not has_healthy_targets:
                # ALB ~$16/month base + LCU charges; NLB ~$16/month
                orphans.append(OrphanResource(
                    resource_id=lb_arn,
                    name=lb_name,
                    resource_type=f"{'ALB' if lb_type == 'application' else 'NLB'}",
                    resource_group=f"{self.account_id}/{self.region}",
                    location=self.region,
                    estimated_monthly_cost_usd=16.20,
                    reason=f"{lb_type.upper()} Load Balancer has no healthy targets in any Target Group",
                    tags={t["Key"]: t["Value"] for t in lb.get("Tags", [])},
                ))

        return orphans

    def find_stopped_vms_still_paying(self) -> list[OrphanResource]:
        """
        EC2 instances in 'stopped' state.
        NOTE: Unlike Azure, stopped EC2 instances do NOT incur compute charges —
        but they DO still pay for attached EBS volumes and Elastic IPs.
        We flag them as optimization opportunities, not wasted spend.
        """
        orphans = []
        paginator = self.ec2.get_paginator("describe_instances")

        for page in paginator.paginate(Filters=[{"Name": "instance-state-name", "Values": ["stopped"]}]):
            for reservation in page["Reservations"]:
                for inst in reservation["Instances"]:
                    name = next(
                        (t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"),
                        inst["InstanceId"]
                    )
                    # Estimate cost of attached EBS
                    ebs_cost = 0
                    for bdm in inst.get("BlockDeviceMappings", []):
                        if bdm.get("Ebs"):
                            ebs_cost += 10  # rough estimate per attached volume

                    # How long has it been stopped?
                    # StateTransitionReason gives a hint: "User initiated (2024-01-15 10:00:00 GMT)"
                    stop_reason = inst.get("StateTransitionReason", "")

                    orphans.append(OrphanResource(
                        resource_id=inst["InstanceId"],
                        name=name,
                        resource_type="EC2 Instance",
                        resource_group=f"{self.account_id}/{self.region}",
                        location=inst.get("Placement", {}).get("AvailabilityZone", self.region),
                        estimated_monthly_cost_usd=round(ebs_cost, 2),
                        reason=f"Stopped EC2 instance ({inst.get('InstanceType')}). "
                               f"No compute charges, but attached EBS volumes still billed (~${ebs_cost}/mo). "
                               f"Consider terminating if no longer needed. {stop_reason}",
                        tags={t["Key"]: t["Value"] for t in inst.get("Tags", [])},
                    ))

        return orphans

    # ─── OPTIMIZATION SUGGESTIONS ─────────────────────────────────────────────

    def suggest_reserved_instances(self) -> list[OptimizationSuggestion]:
        """
        Use AWS Cost Explorer's built-in RI recommendations API.
        This is more accurate than manual calculation because AWS knows
        the actual On-Demand price for every instance type/region.
        """
        suggestions = []
        try:
            response = self.ce.get_reservation_purchase_recommendation(
                Service="Amazon EC2",
                LookbackPeriodInDays="THIRTY_DAYS",
                TermInYears="ONE_YEAR",
                PaymentOption="NO_UPFRONT",
            )

            for rec_group in response.get("Recommendations", []):
                for detail in rec_group.get("RecommendationDetails", []):
                    instance_type = detail.get("InstanceDetails", {}).get(
                        "EC2InstanceDetails", {}
                    ).get("InstanceType", "Unknown")
                    region = detail.get("InstanceDetails", {}).get(
                        "EC2InstanceDetails", {}
                    ).get("Region", self.region)
                    savings = float(detail.get("EstimatedMonthlySavingsAmount", 0))
                    on_demand = float(detail.get("EstimatedMonthlyOnDemandCost", 0))
                    uptime_pct = float(detail.get("UpfrontCost", 0))

                    if savings < 5:  # Skip tiny recommendations
                        continue

                    suggestions.append(OptimizationSuggestion(
                        resource_id=f"ri-rec-{instance_type}-{region}",
                        resource_name=f"{instance_type} in {region}",
                        suggestion_type="reserved_instance",
                        current_cost_monthly=round(on_demand, 2),
                        estimated_savings_monthly=round(savings, 2),
                        confidence="high",
                        detail=f"AWS recommends purchasing a 1-year No-Upfront RI for {instance_type} "
                               f"in {region}. Savings vs On-Demand: ~${savings:.0f}/mo "
                               f"({(savings/on_demand*100) if on_demand else 0:.0f}%)",
                    ))

        except ClientError as e:
            logger.warning(f"[AWS] RI recommendations unavailable: {e}")
            # Fallback: manual check of long-running instances via CloudWatch
            suggestions.extend(self._manual_ri_suggestions())

        return suggestions

    def _manual_ri_suggestions(self) -> list[OptimizationSuggestion]:
        """Fallback: find On-Demand instances running >80% of the month via CloudWatch."""
        suggestions = []
        paginator = self.ec2.get_paginator("describe_instances")
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=30)

        for page in paginator.paginate(Filters=[{"Name": "instance-state-name", "Values": ["running"]}]):
            for reservation in page["Reservations"]:
                for inst in reservation["Instances"]:
                    # Skip already Reserved instances
                    if inst.get("InstanceLifecycle") in ("spot", "scheduled"):
                        continue

                    try:
                        metrics = self.cw.get_metric_statistics(
                            Namespace="AWS/EC2",
                            MetricName="CPUUtilization",
                            Dimensions=[{"Name": "InstanceId", "Value": inst["InstanceId"]}],
                            StartTime=start,
                            EndTime=end,
                            Period=86400,  # daily
                            Statistics=["Average"],
                        )
                        data_points = metrics.get("Datapoints", [])
                        if len(data_points) >= 24:  # ran 24+ of 30 days
                            instance_type = inst.get("InstanceType", "unknown")
                            # Rough On-Demand price (varies; real impl should query AWS Price List API)
                            est_monthly = 100.0
                            savings = est_monthly * 0.38  # ~38% savings for 1yr no-upfront

                            name = next(
                                (t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"),
                                inst["InstanceId"]
                            )
                            suggestions.append(OptimizationSuggestion(
                                resource_id=inst["InstanceId"],
                                resource_name=name,
                                suggestion_type="reserved_instance",
                                current_cost_monthly=est_monthly,
                                estimated_savings_monthly=round(savings, 2),
                                confidence="medium",
                                detail=f"{instance_type} ran {len(data_points)}/30 days. "
                                       f"1-year No-Upfront RI could save ~38% (~${savings:.0f}/mo)",
                            ))
                    except Exception as e:
                        logger.debug(f"[AWS] Could not get metrics for {inst['InstanceId']}: {e}")

        return suggestions

    def find_underutilized_rds(self) -> list[OptimizationSuggestion]:
        """Find RDS instances with very low CPU — candidates for downsizing."""
        suggestions = []
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=14)

        try:
            dbs = self.rds.describe_db_instances().get("DBInstances", [])
        except ClientError:
            return []

        for db in dbs:
            db_id = db["DBInstanceIdentifier"]
            db_class = db["DBInstanceClass"]

            try:
                metrics = self.cw.get_metric_statistics(
                    Namespace="AWS/RDS",
                    MetricName="CPUUtilization",
                    Dimensions=[{"Name": "DBInstanceIdentifier", "Value": db_id}],
                    StartTime=start,
                    EndTime=end,
                    Period=86400,
                    Statistics=["Average"],
                )
                data_points = metrics.get("Datapoints", [])
                if not data_points:
                    continue

                avg_cpu = sum(d["Average"] for d in data_points) / len(data_points)

                if avg_cpu < 10:  # Less than 10% average CPU
                    # Rough estimate: db.t3.medium ~$50/mo, downsizing could save 30-50%
                    est_current = 80.0
                    savings = est_current * 0.40

                    suggestions.append(OptimizationSuggestion(
                        resource_id=db_id,
                        resource_name=db_id,
                        suggestion_type="rightsize",
                        current_cost_monthly=est_current,
                        estimated_savings_monthly=round(savings, 2),
                        confidence="medium" if avg_cpu < 5 else "low",
                        detail=f"RDS {db_class} avg CPU: {avg_cpu:.1f}% over 14 days. "
                               f"Consider downsizing to a smaller instance class (~${savings:.0f}/mo savings).",
                    ))

            except Exception as e:
                logger.debug(f"[AWS] Could not get RDS metrics for {db_id}: {e}")

        return suggestions
