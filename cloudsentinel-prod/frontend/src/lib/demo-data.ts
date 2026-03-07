// src/lib/demo-data.ts
// Realistic simulated data for the demo account

export const DEMO_EMAIL = 'demo@cloudsentinel.io';

export const demoConnections = [
  { id: 'demo-conn-1', provider: 'azure' as const, display_name: 'Production — Azure East US', account_identifier: 'sub-a1b2c3d4', is_active: true, last_scan_at: new Date(Date.now() - 3600000).toISOString(), created_at: new Date(Date.now() - 86400000 * 30).toISOString() },
  { id: 'demo-conn-2', provider: 'aws'   as const, display_name: 'AWS — us-east-1',            account_identifier: '123456789012',  is_active: true, last_scan_at: new Date(Date.now() - 7200000).toISOString(), created_at: new Date(Date.now() - 86400000 * 20).toISOString() },
  { id: 'demo-conn-3', provider: 'gcp'   as const, display_name: 'GCP — my-startup-prod',      account_identifier: 'my-startup-prod', is_active: true, last_scan_at: new Date(Date.now() - 1800000).toISOString(), created_at: new Date(Date.now() - 86400000 * 10).toISOString() },
];

export const demoSummary = {
  total_spend_30d: 18420,
  total_savings_identified: 4310,
  total_orphan_count: 23,
  connection_count: 3,
  tier: 'pro',
  latest_reports: [
    { id: 'r1', provider: 'azure', report_type: 'weekly', period_start: '', period_end: '', total_spend: 9800,  total_savings_identified: 2100, orphan_count: 12, anomaly_detected: true,  created_at: new Date(Date.now() - 86400000).toISOString(), connection_name: 'Production — Azure East US' },
    { id: 'r2', provider: 'aws',   report_type: 'weekly', period_start: '', period_end: '', total_spend: 5300,  total_savings_identified: 1400, orphan_count: 7,  anomaly_detected: false, created_at: new Date(Date.now() - 86400000).toISOString(), connection_name: 'AWS — us-east-1' },
    { id: 'r3', provider: 'gcp',   report_type: 'weekly', period_start: '', period_end: '', total_spend: 3320,  total_savings_identified: 810,  orphan_count: 4,  anomaly_detected: false, created_at: new Date(Date.now() - 86400000).toISOString(), connection_name: 'GCP — my-startup-prod' },
  ],
};

export const demoReport = {
  id: 'demo-report-1',
  provider: 'azure',
  report_type: 'weekly',
  period_start: new Date(Date.now() - 86400000 * 30).toISOString(),
  period_end:   new Date().toISOString(),
  total_spend: 18420,
  total_savings_identified: 4310,
  orphan_count: 23,
  anomaly_detected: true,
  created_at: new Date(Date.now() - 86400000).toISOString(),
  report_data: {
    total_spend_30d: 18420,
    total_potential_savings: 4310,
    cost_by_service: [
      { service: 'Virtual Machines',    total_cost: 7200,  percentage: 39 },
      { service: 'Storage Accounts',    total_cost: 3100,  percentage: 17 },
      { service: 'SQL Database',        total_cost: 2800,  percentage: 15 },
      { service: 'Load Balancer',       total_cost: 1900,  percentage: 10 },
      { service: 'Kubernetes Service',  total_cost: 1620,  percentage: 9  },
      { service: 'Other',               total_cost: 1800,  percentage: 10 },
    ],
    anomaly_alert: {
      delta_pct: 34,
      yesterday_spend: 820,
      avg_7day_spend: 612,
      severity: 'high',
    },
    orphan_resources: {
      unattached_disks: [
        { resource_id: 'd1', name: 'datadisk-old-prod-01',   resource_type: 'Managed Disk',  resource_group: 'rg-production', location: 'eastus',    estimated_monthly_cost_usd: 48.50,  reason: 'Unattached for 47 days', tags: {} },
        { resource_id: 'd2', name: 'backup-disk-staging-02', resource_type: 'Managed Disk',  resource_group: 'rg-staging',    location: 'westus2',   estimated_monthly_cost_usd: 32.00,  reason: 'Unattached for 23 days', tags: {} },
        { resource_id: 'd3', name: 'temp-migration-disk',    resource_type: 'Managed Disk',  resource_group: 'rg-migration',  location: 'eastus2',   estimated_monthly_cost_usd: 18.75,  reason: 'Unattached for 91 days', tags: {} },
        { resource_id: 'd4', name: 'ebs-vol-i-0abc123def',   resource_type: 'EBS Volume',    resource_group: 'us-east-1',     location: 'us-east-1', estimated_monthly_cost_usd: 55.20,  reason: 'Available state, no instance attached', tags: {} },
        { resource_id: 'd5', name: 'ebs-vol-i-0def456abc',   resource_type: 'EBS Volume',    resource_group: 'us-east-1',     location: 'us-east-1', estimated_monthly_cost_usd: 28.40,  reason: 'Available state, no instance attached', tags: {} },
      ],
      idle_public_ips: [
        { resource_id: 'ip1', name: 'pip-old-gateway',       resource_type: 'Public IP',     resource_group: 'rg-network',    location: 'eastus',    estimated_monthly_cost_usd: 3.65,   reason: 'Not associated with any resource', tags: {} },
        { resource_id: 'ip2', name: 'eip-i-0123456789',      resource_type: 'Elastic IP',    resource_group: 'us-east-1',     location: 'us-east-1', estimated_monthly_cost_usd: 3.65,   reason: 'Not associated with any instance', tags: {} },
        { resource_id: 'ip3', name: 'static-ip-old-service', resource_type: 'Static IP',     resource_group: 'us-central1',   location: 'us-central1', estimated_monthly_cost_usd: 7.30, reason: 'RESERVED status, not in use', tags: {} },
      ],
      idle_load_balancers: [
        { resource_id: 'lb1', name: 'lb-legacy-api-v1',      resource_type: 'Load Balancer', resource_group: 'rg-production', location: 'eastus',    estimated_monthly_cost_usd: 182.50, reason: 'No backend instances for 14 days', tags: {} },
        { resource_id: 'lb2', name: 'alb-old-microservice',  resource_type: 'ALB',           resource_group: 'us-east-1',     location: 'us-east-1', estimated_monthly_cost_usd: 165.00, reason: 'No healthy targets in any target group', tags: {} },
      ],
      stopped_vms: [
        { resource_id: 'vm1', name: 'vm-dev-testing-01',     resource_type: 'Virtual Machine', resource_group: 'rg-dev',      location: 'eastus',    estimated_monthly_cost_usd: 142.80, reason: 'Stopped (not deallocated) — still incurring compute charges', tags: { env: 'dev' } },
        { resource_id: 'vm2', name: 'vm-staging-worker-03',  resource_type: 'Virtual Machine', resource_group: 'rg-staging',  location: 'westus2',   estimated_monthly_cost_usd: 89.60,  reason: 'Stopped (not deallocated) — still incurring compute charges', tags: { env: 'staging' } },
        { resource_id: 'vm3', name: 'vm-old-batch-jobs',     resource_type: 'Virtual Machine', resource_group: 'rg-legacy',   location: 'eastus2',   estimated_monthly_cost_usd: 210.40, reason: 'Stopped (not deallocated) for 62 days', tags: {} },
      ],
    },
    optimization_suggestions: [
      { resource_id: 'vm-prod-web-01', resource_name: 'vm-prod-web-01',    suggestion_type: 'Reserved Instance', current_cost_monthly: 380.00, estimated_savings_monthly: 273.60, confidence: 'high',   detail: 'Running 24/7 for 90+ days. Switch to 1-year Reserved Instance for 72% savings.' },
      { resource_id: 'vm-prod-api-02', resource_name: 'vm-prod-api-02',    suggestion_type: 'Reserved Instance', current_cost_monthly: 285.00, estimated_savings_monthly: 205.20, confidence: 'high',   detail: 'Consistent usage pattern. 1-year RI recommended.' },
      { resource_id: 'i-0abc123def456', resource_name: 'ec2-worker-large', suggestion_type: 'Right-Size',        current_cost_monthly: 420.00, estimated_savings_monthly: 210.00, confidence: 'medium', detail: 'Average CPU utilization 12% over 30 days. Downsize from c5.2xlarge to c5.large.' },
      { resource_id: 'vm-dev-unused',  resource_name: 'vm-dev-unused',     suggestion_type: 'Auto-Shutdown',     current_cost_monthly: 95.00,  estimated_savings_monthly: 66.50,  confidence: 'high',   detail: 'No activity detected outside 09:00–18:00. Schedule auto-shutdown to save 70%.' },
      { resource_id: 'db-prod-01',     resource_name: 'sql-prod-primary',  suggestion_type: 'Reserved Instance', current_cost_monthly: 650.00, estimated_savings_monthly: 351.00, confidence: 'high',   detail: 'Production database running 24/7. 1-year reserved capacity saves 54%.' },
    ],
  },
};

export const demoReports = demoSummary.latest_reports.map(r => ({
  ...r,
  period_start: new Date(Date.now() - 86400000 * 30).toISOString(),
  period_end:   new Date().toISOString(),
}));
