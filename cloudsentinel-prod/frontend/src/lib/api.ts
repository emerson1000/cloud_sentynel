// src/lib/api.ts
// All HTTP calls to the FastAPI backend go through here.
// The JWT from Supabase is automatically attached to every request.

import { createClient } from '@/lib/supabase/client';

const BASE = process.env.NEXT_PUBLIC_API_URL;

async function getAuthHeader(): Promise<string> {
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) throw new Error('Not authenticated');
  return `Bearer ${session.access_token}`;
}

async function request<T>(
  method: 'GET' | 'POST' | 'PUT' | 'DELETE',
  path: string,
  body?: unknown
): Promise<T> {
  const auth = await getAuthHeader();
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      Authorization: auth,
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Connections ───────────────────────────────────────────────────────────────
export const api = {
  connections: {
    list: ()                 => request<Connection[]>('GET',  '/api/connections'),
    add:  (body: AddConn)   => request<{ connection: Connection }>('POST', '/api/connections', body),
    del:  (id: string)      => request<void>('DELETE', `/api/connections/${id}`),
  },

  reports: {
    list: (connId?: string) => request<Report[]>('GET', `/api/reports${connId ? `?connection_id=${connId}` : ''}`),
    get:  (id: string)      => request<ReportDetail>('GET', `/api/reports/${id}`),
  },

  dashboard: {
    summary: ()             => request<DashboardSummary>('GET', '/api/dashboard/summary'),
  },

  alerts: {
    update: (body: AlertConfig) => request<void>('PUT', '/api/alert-config', body),
    get:    (connId: string)    => request<AlertConfig>('GET', `/api/alert-config/${connId}`),
  },

  scan: {
    trigger: (connId: string) => request<{ report_id: string; report: ReportDetail }>(
      'POST', '/api/scan', { connection_id: connId }
    ),
  },
};

// ── Types ─────────────────────────────────────────────────────────────────────
export interface Connection {
  id: string;
  provider: 'azure' | 'aws' | 'gcp';
  display_name: string;
  account_identifier: string;
  is_active: boolean;
  last_scan_at: string | null;
  created_at: string;
}

export interface AddConn {
  provider: 'azure' | 'aws' | 'gcp';
  display_name: string;
  // Azure
  subscription_id?: string;
  tenant_id?: string;
  client_id?: string;
  client_secret?: string;
  // AWS
  aws_access_key_id?: string;
  aws_secret_access_key?: string;
  aws_region?: string;
  // GCP
  project_id?: string;
  billing_account_id?: string;
  service_account_json?: object;
}

export interface Report {
  id: string;
  provider: string;
  report_type: string;
  period_start: string;
  period_end: string;
  total_spend: number;
  total_savings_identified: number;
  orphan_count: number;
  anomaly_detected: boolean;
  created_at: string;
}

export interface ReportDetail extends Report {
  report_data: {
    cost_by_service: Array<{ service: string; total_cost: number; percentage: number }>;
    anomaly_alert: { delta_pct: number; yesterday_spend: number; avg_7day_spend: number; severity: string } | null;
    orphan_resources: {
      unattached_disks: OrphanResource[];
      idle_public_ips: OrphanResource[];
      idle_load_balancers: OrphanResource[];
      stopped_vms: OrphanResource[];
    };
    optimization_suggestions: Suggestion[];
    total_spend_30d: number;
    total_potential_savings: number;
  };
}

export interface OrphanResource {
  resource_id: string;
  name: string;
  resource_type: string;
  resource_group: string;
  location: string;
  estimated_monthly_cost_usd: number;
  reason: string;
  tags: Record<string, string>;
}

export interface Suggestion {
  resource_id: string;
  resource_name: string;
  suggestion_type: string;
  current_cost_monthly: number;
  estimated_savings_monthly: number;
  confidence: string;
  detail: string;
}

export interface AlertConfig {
  connection_id: string;
  anomaly_threshold_pct: number;
  notify_email: boolean;
  notify_telegram: boolean;
  telegram_chat_id?: string;
}

export interface DashboardSummary {
  total_spend_30d: number;
  total_savings_identified: number;
  total_orphan_count: number;
  connection_count: number;
  tier: string;
  latest_reports: (Report & { connection_name: string })[];
}
