'use client';
// src/app/dashboard/page.tsx

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import toast from 'react-hot-toast';
import { api, type DashboardSummary, type ReportDetail } from '@/lib/api';
import { KpiCard }        from '@/components/ui/KpiCard';
import { SpendChart }     from '@/components/charts/SpendChart';
import { ServiceDonut }   from '@/components/charts/ServiceDonut';
import { ZombieRow }      from '@/components/ui/ZombieRow';
import { AnomalyBanner }  from '@/components/ui/AnomalyBanner';
import { ScanButton }     from '@/components/ui/ScanButton';

export default function DashboardPage() {
  const router = useRouter();
  const [summary,  setSummary]  = useState<DashboardSummary | null>(null);
  const [report,   setReport]   = useState<ReportDetail | null>(null);
  const [loading,  setLoading]  = useState(true);
  const [dimAlert, setDimAlert] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [sum, reports] = await Promise.all([
        api.dashboard.summary(),
        api.reports.list(undefined),
      ]);
      setSummary(sum);
      if (reports[0]) {
        const detail = await api.reports.get(reports[0].id);
        setReport(detail);
      }
    } catch (err: any) {
      // If no connections yet → redirect to onboarding
      if (err.message?.includes('no connections') || err.message?.includes('404')) {
        router.push('/onboarding');
      }
      // Otherwise show whatever partial data we have
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LoadingSkeleton />;
  if (!summary) return <EmptyState onConnect={() => router.push('/onboarding')} />;

  const rd    = report?.report_data;
  const allOrphans = rd ? [
    ...rd.orphan_resources.unattached_disks,
    ...rd.orphan_resources.idle_public_ips,
    ...rd.orphan_resources.idle_load_balancers,
    ...rd.orphan_resources.stopped_vms,
  ] : [];

  return (
    <div className="animate-fade-in flex flex-col gap-4">
      {/* Anomaly banner */}
      {!dimAlert && rd?.anomaly_alert && (
        <AnomalyBanner anomaly={rd.anomaly_alert} onDismiss={() => setDimAlert(true)} />
      )}

      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="font-display font-bold text-xl text-[#f1f5f9]">Cost Intelligence Dashboard</h1>
          <p className="text-[11px] text-[#334155] tracking-[.05em] mt-1">LAST 30 DAYS · {summary.connection_count} CONNECTION{summary.connection_count !== 1 ? 'S' : ''} ACTIVE</p>
        </div>
        <ScanButton onScanComplete={loadData} />
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard icon="💰" label="30-Day Spend"     value={`$${summary.total_spend_30d.toLocaleString()}`} sub={`${summary.connection_count} subscriptions`} color="text-[#e2e8f0]" />
        <KpiCard icon="💡" label="Savings Found"    value={`$${summary.total_savings_identified.toLocaleString()}`} sub="per month recoverable" color="text-[#34d399]" />
        <KpiCard icon="🧟" label="Zombies"          value={summary.total_orphan_count} sub={`$${allOrphans.reduce((s,o)=>s+o.estimated_monthly_cost_usd,0).toFixed(0)}/mo wasted`} color="text-[#f87171]" />
        <KpiCard icon="⚡" label="Optimizations"   value={rd?.optimization_suggestions.length ?? 0} sub={`$${(rd?.total_potential_savings ?? 0).toFixed(0)}/mo potential`} color="text-[#a78bfa]" />
      </div>

      {/* Charts */}
      {rd && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          <div className="lg:col-span-2 bg-[#060d1a] border border-[#0d2340] rounded-xl p-5">
            <div className="flex justify-between items-center mb-4">
              <p className="text-[10px] text-[#334155] tracking-[.1em] uppercase">Daily Spend · 30 Days</p>
              <p className="text-[10px] text-[#334155]">Avg ${((rd.total_spend_30d) / 30).toFixed(0)}/day · <span className="text-[#ef4444]">● anomalies</span></p>
            </div>
            <SpendChart services={rd.cost_by_service} totalSpend={rd.total_spend_30d} />
          </div>
          <div className="bg-[#060d1a] border border-[#0d2340] rounded-xl p-5">
            <p className="text-[10px] text-[#334155] tracking-[.1em] uppercase mb-4">Spend by Service</p>
            <ServiceDonut data={rd.cost_by_service} />
          </div>
        </div>
      )}

      {/* Top zombies */}
      {allOrphans.length > 0 && (
        <div className="bg-[#060d1a] border border-[#0d2340] rounded-xl p-5">
          <div className="flex justify-between items-center mb-4">
            <p className="text-[10px] text-[#334155] tracking-[.1em] uppercase">Top Zombie Resources</p>
            <a href="/dashboard/zombies" className="text-[11px] text-[#f59e0b] hover:underline">See all {summary.total_orphan_count} →</a>
          </div>
          <div className="flex flex-col gap-2">
            {allOrphans
              .sort((a,b) => b.estimated_monthly_cost_usd - a.estimated_monthly_cost_usd)
              .slice(0, 4)
              .map((o,i) => <ZombieRow key={i} resource={o} />)
            }
          </div>
        </div>
      )}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="flex flex-col gap-4 animate-pulse">
      <div className="grid grid-cols-4 gap-3">
        {[...Array(4)].map((_,i) => <div key={i} className="h-24 bg-[#060d1a] rounded-xl border border-[#0d2340]" />)}
      </div>
      <div className="h-52 bg-[#060d1a] rounded-xl border border-[#0d2340]" />
    </div>
  );
}

function EmptyState({ onConnect }: { onConnect: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-5 text-center py-20">
      <div className="text-5xl">☁</div>
      <div>
        <p className="font-display font-bold text-xl text-[#f1f5f9] mb-2">No cloud connections yet</p>
        <p className="text-sm text-[#475569]">Connect your first Azure, AWS or GCP account to start scanning.</p>
      </div>
      <button onClick={onConnect} className="bg-[#f59e0b] text-[#03070f] font-mono font-medium text-sm px-8 py-3 rounded-lg tracking-[.07em] hover:bg-[#fbbf24] transition-colors">
        Connect your cloud →
      </button>
    </div>
  );
}
