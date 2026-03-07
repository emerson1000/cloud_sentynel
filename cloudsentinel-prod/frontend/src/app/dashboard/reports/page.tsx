'use client';
// src/app/dashboard/reports/page.tsx
import { useEffect, useState } from 'react';
import { api, type Report } from '@/lib/api';
import { format } from 'date-fns';

export default function ReportsPage() {
  const [reports, setReports] = useState<(Report & {connection_name?:string})[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.reports.list().then(setReports).catch(()=>{}).finally(()=>setLoading(false));
  }, []);

  if (loading) return <div className="animate-pulse space-y-2">{[...Array(5)].map((_,i)=><div key={i} className="h-12 bg-[#060d1a] rounded-xl border border-[#0d2340]"/>)}</div>;

  return (
    <div className="animate-fade-in">
      <div className="bg-[#060d1a] border border-[#0d2340] rounded-xl overflow-hidden">
        <div className="grid px-5 py-3 bg-[#03070f] border-b border-[#0a1628]" style={{gridTemplateColumns:'1fr 1fr 1fr 1fr 80px'}}>
          {['Date','Type','Spend','Savings Found','Anomaly'].map(h=><span key={h} className="text-[10px] text-[#1e3a5f] tracking-[.1em] uppercase">{h}</span>)}
        </div>
        {reports.length === 0 ? (
          <div className="text-center py-14 text-[#334155] text-sm">No reports yet. Run a scan to generate your first report.</div>
        ) : reports.map((r,i)=>(
          <div key={i} className="grid px-5 py-3 border-b border-[#06101e] items-center hover:bg-[#060d1a]/50 transition-colors" style={{gridTemplateColumns:'1fr 1fr 1fr 1fr 80px'}}>
            <span className="text-xs text-[#94a3b8]">{format(new Date(r.created_at), 'MMM d, yyyy')}</span>
            <span className="text-[11px] text-[#475569] tracking-[.03em]">{r.report_type}</span>
            <span className="text-[13px] font-semibold">${r.total_spend.toLocaleString()}</span>
            <span className={`text-[13px] font-semibold ${r.total_savings_identified > 0 ? 'text-[#34d399]' : 'text-[#1e3a5f]'}`}>
              {r.total_savings_identified > 0 ? `$${r.total_savings_identified.toLocaleString()}` : '—'}
            </span>
            <span>{r.anomaly_detected
              ? <span className="text-[#f87171] text-[11px] font-bold">⚠ YES</span>
              : <span className="text-[#1e3a5f] text-[11px]">—</span>}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
