'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, type DashboardSummary, type ReportDetail } from '@/lib/api';
import { useIsDemo } from '@/hooks/useDemo';
import { demoSummary, demoReport } from '@/lib/demo-data';
import { KpiCard }       from '@/components/ui/KpiCard';
import { SpendChart }    from '@/components/charts/SpendChart';
import { ServiceDonut }  from '@/components/charts/ServiceDonut';
import { ZombieRow }     from '@/components/ui/ZombieRow';
import { AnomalyBanner } from '@/components/ui/AnomalyBanner';
import { ScanButton }    from '@/components/ui/ScanButton';

export default function DashboardPage() {
  const router = useRouter();
  const { isDemo, loading: demoLoading } = useIsDemo();
  const [summary,  setSummary]  = useState<DashboardSummary | null>(null);
  const [report,   setReport]   = useState<ReportDetail | null>(null);
  const [loading,  setLoading]  = useState(true);
  const [dimAlert, setDimAlert] = useState(false);

  useEffect(() => {
    if (demoLoading) return;
    if (isDemo) {
      setSummary(demoSummary as any);
      setReport(demoReport as any);
      setLoading(false);
      return;
    }
    loadData();
  }, [isDemo, demoLoading]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [sum, reports] = await Promise.all([api.dashboard.summary(), api.reports.list(undefined)]);
      setSummary(sum);
      if (reports[0]) { const detail = await api.reports.get(reports[0].id); setReport(detail); }
    } catch { router.push('/onboarding'); }
    finally { setLoading(false); }
  };

  if (loading || demoLoading) return <div className="animate-pulse grid grid-cols-4 gap-3">{[...Array(4)].map((_,i)=><div key={i} className="h-24 bg-[#060d1a] rounded-xl border border-[#0d2340]"/>)}</div>;
  if (!summary) return <div className="text-center py-20"><p className="text-4xl mb-3">☁</p><p className="font-display font-bold text-xl text-[#f1f5f9] mb-2">No cloud connections yet</p><button onClick={()=>router.push('/onboarding')} className="mt-4 bg-[#f59e0b] text-[#03070f] font-mono font-medium text-sm px-8 py-3 rounded-lg hover:bg-[#fbbf24]">Connect your cloud →</button></div>;

  const rd = report?.report_data;
  const allOrphans = rd ? [...rd.orphan_resources.unattached_disks,...rd.orphan_resources.idle_public_ips,...rd.orphan_resources.idle_load_balancers,...rd.orphan_resources.stopped_vms] : [];

  return (
    <div className="animate-fade-in flex flex-col gap-4">
      {isDemo && <div className="bg-[#0a1f0a] border border-[#14532d]/40 rounded-lg px-4 py-2.5 text-xs text-[#86efac]">🎮 Demo mode — simulated data for 3 cloud accounts (Azure + AWS + GCP)</div>}
      {!dimAlert && rd?.anomaly_alert && <AnomalyBanner anomaly={rd.anomaly_alert} onDismiss={() => setDimAlert(true)} />}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="font-display font-bold text-xl text-[#f1f5f9]">Cost Intelligence Dashboard</h1>
          <p className="text-[11px] text-[#334155] mt-1">LAST 30 DAYS · {summary.connection_count} CONNECTIONS ACTIVE</p>
        </div>
        {!isDemo && <ScanButton onScanComplete={loadData} />}
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard icon="💰" label="30-Day Spend"   value={`$${summary.total_spend_30d.toLocaleString()}`}          sub={`${summary.connection_count} accounts`} color="text-[#e2e8f0]" />
        <KpiCard icon="💡" label="Savings Found"  value={`$${summary.total_savings_identified.toLocaleString()}`} sub="per month recoverable"                  color="text-[#34d399]" />
        <KpiCard icon="🧟" label="Zombies"        value={summary.total_orphan_count}                              sub={`$${allOrphans.reduce((s,o)=>s+o.estimated_monthly_cost_usd,0).toFixed(0)}/mo wasted`} color="text-[#f87171]" />
        <KpiCard icon="⚡" label="Optimizations" value={rd?.optimization_suggestions.length ?? 0}                sub={`$${(rd?.total_potential_savings??0).toFixed(0)}/mo potential`} color="text-[#a78bfa]" />
      </div>
      {rd && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          <div className="lg:col-span-2 bg-[#060d1a] border border-[#0d2340] rounded-xl p-5">
            <p className="text-[10px] text-[#334155] tracking-[.1em] uppercase mb-4">Daily Spend · 30 Days</p>
            <SpendChart services={rd.cost_by_service} totalSpend={rd.total_spend_30d} />
          </div>
          <div className="bg-[#060d1a] border border-[#0d2340] rounded-xl p-5">
            <p className="text-[10px] text-[#334155] tracking-[.1em] uppercase mb-4">Spend by Service</p>
            <ServiceDonut data={rd.cost_by_service} />
          </div>
        </div>
      )}
      {allOrphans.length > 0 && (
        <div className="bg-[#060d1a] border border-[#0d2340] rounded-xl p-5">
          <div className="flex justify-between items-center mb-4">
            <p className="text-[10px] text-[#334155] tracking-[.1em] uppercase">Top Zombie Resources</p>
            <a href="/dashboard/zombies" className="text-[11px] text-[#f59e0b] hover:underline">See all {summary.total_orphan_count} →</a>
          </div>
          <div className="flex flex-col gap-2">
            {allOrphans.sort((a,b)=>b.estimated_monthly_cost_usd-a.estimated_monthly_cost_usd).slice(0,4).map((o,i)=><ZombieRow key={i} resource={o}/>)}
          </div>
        </div>
      )}
    </div>
  );
}
