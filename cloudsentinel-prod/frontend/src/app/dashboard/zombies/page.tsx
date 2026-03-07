'use client';
// src/app/dashboard/zombies/page.tsx
import { useEffect, useState } from 'react';
import { api, type OrphanResource } from '@/lib/api';

const SEV: Record<string, [string,string]> = {
  critical:['#450a0a','#fca5a5'], high:['#431407','#fb923c'],
  medium:  ['#422006','#fbbf24'], low: ['#0c1a2e','#60a5fa'],
};
function getSev(r: OrphanResource) {
  if (r.resource_type.toLowerCase().includes('virtual') && r.reason.toLowerCase().includes('stopped')) return 'critical';
  if (r.estimated_monthly_cost_usd > 50) return 'high';
  if (r.estimated_monthly_cost_usd > 15) return 'medium';
  return 'low';
}

export default function ZombiesPage() {
  const [orphans, setOrphans] = useState<OrphanResource[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.reports.list().then(async reports => {
      if (!reports[0]) { setLoading(false); return; }
      const detail = await api.reports.get(reports[0].id);
      const all = [
        ...detail.report_data.orphan_resources.unattached_disks,
        ...detail.report_data.orphan_resources.idle_public_ips,
        ...detail.report_data.orphan_resources.idle_load_balancers,
        ...detail.report_data.orphan_resources.stopped_vms,
      ];
      const sevOrder = {critical:0,high:1,medium:2,low:3};
      all.sort((a,b) => sevOrder[getSev(a) as keyof typeof sevOrder] - sevOrder[getSev(b) as keyof typeof sevOrder]);
      setOrphans(all);
    }).catch(()=>{}).finally(()=>setLoading(false));
  }, []);

  const totalCost = orphans.reduce((s,o) => s + o.estimated_monthly_cost_usd, 0);

  if (loading) return <div className="animate-pulse space-y-3">{[...Array(5)].map((_,i)=><div key={i} className="h-14 bg-[#060d1a] rounded-xl border border-[#0d2340]"/>)}</div>;

  return (
    <div className="animate-fade-in flex flex-col gap-4">
      <div className="text-sm text-[#64748b]">
        Found <strong className="text-[#f87171]">{orphans.length} zombie resources</strong> costing <strong className="text-[#f87171]">${totalCost.toFixed(2)}/month (${(totalCost*12).toFixed(0)}/year)</strong>
      </div>

      <div className="bg-[#060d1a] border border-[#0d2340] rounded-xl overflow-hidden">
        {/* Header */}
        <div className="grid px-5 py-3 bg-[#03070f] border-b border-[#0a1628]" style={{gridTemplateColumns:'2fr 1fr 1fr 1fr 100px'}}>
          {['Resource','Type','Group / Project','Monthly Cost','Severity'].map(h => (
            <span key={h} className="text-[10px] text-[#1e3a5f] tracking-[.1em] uppercase">{h}</span>
          ))}
        </div>
        {orphans.length === 0 ? (
          <div className="text-center py-16 text-[#334155]">
            <div className="text-4xl mb-3">🎉</div>
            <p className="text-sm">No zombie resources found! Your cloud is clean.</p>
          </div>
        ) : orphans.map((o,i) => {
          const sev = getSev(o);
          const [bg,color] = SEV[sev];
          return (
            <div key={i} className="grid px-5 py-3 border-b border-[#06101e] items-center hover:bg-[#060d1a] transition-colors" style={{gridTemplateColumns:'2fr 1fr 1fr 1fr 100px'}}>
              <div>
                <p className="text-[12px] font-medium text-[#e2e8f0]">{o.name}</p>
                <p className="text-[10px] text-[#334155] mt-0.5">{o.reason}</p>
              </div>
              <span className="text-[11px] text-[#475569]">{o.resource_type}</span>
              <span className="text-[11px] text-[#334155]">{o.resource_group}</span>
              <span className="text-[13px] text-[#f87171] font-bold">${o.estimated_monthly_cost_usd.toFixed(2)}</span>
              <span style={{background:bg,color,fontSize:10,fontWeight:700,padding:'2px 8px',borderRadius:4,letterSpacing:'.06em',textTransform:'uppercase',display:'inline-block'}}>{sev}</span>
            </div>
          );
        })}
      </div>

      {orphans.length > 0 && (
        <div className="p-3.5 bg-[#0a1f0a] border border-[#14532d]/40 rounded-lg text-xs text-[#86efac]">
          💡 Deleting all zombie resources saves <strong>${totalCost.toFixed(2)}/month</strong> — that's <strong>${(totalCost*12).toFixed(0)}/year</strong>
        </div>
      )}
    </div>
  );
}
