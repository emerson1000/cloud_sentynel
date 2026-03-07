'use client';
// src/app/dashboard/optimize/page.tsx
import { useEffect, useState } from 'react';
import { api, type Suggestion } from '@/lib/api';

const TYPE_CFG: Record<string,[string,string]> = {
  'Reserved Instance': ['#f59e0b','🏦'],
  'Right-Size':        ['#60a5fa','📐'],
  'Auto-Shutdown':     ['#34d399','🕐'],
};

export default function OptimizePage() {
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [loading,     setLoading]     = useState(true);

  useEffect(() => {
    api.reports.list().then(async reports => {
      if (!reports[0]) { setLoading(false); return; }
      const detail = await api.reports.get(reports[0].id);
      setSuggestions(detail.report_data.optimization_suggestions);
    }).catch(()=>{}).finally(()=>setLoading(false));
  }, []);

  const totalSavings = suggestions.reduce((s,sg) => s + sg.estimated_savings_monthly, 0);

  if (loading) return <div className="animate-pulse space-y-3">{[...Array(4)].map((_,i)=><div key={i} className="h-20 bg-[#060d1a] rounded-xl border border-[#0d2340]"/>)}</div>;

  return (
    <div className="animate-fade-in flex flex-col gap-4">
      <div className="text-sm text-[#64748b]">
        <strong className="text-[#a78bfa]">{suggestions.length} opportunities</strong> — save up to <strong className="text-[#34d399]">${totalSavings.toFixed(0)}/month</strong>
      </div>

      {suggestions.length === 0 ? (
        <div className="text-center py-20 text-[#334155]">
          <div className="text-4xl mb-3">✨</div>
          <p className="text-sm">No optimization opportunities found yet. Run a scan to check.</p>
        </div>
      ) : suggestions.map((s,i) => {
        const [color,icon] = TYPE_CFG[s.suggestion_type] || ['#94a3b8','💡'];
        return (
          <div key={i} className="bg-[#060d1a] border border-[#0d2340] rounded-xl px-5 py-4 flex justify-between items-center gap-4 hover:border-[#0d2f50] transition-colors">
            <div className="flex gap-4 items-start min-w-0">
              <div className="shrink-0 p-2.5 rounded-xl text-xl" style={{background:`${color}18`,border:`1px solid ${color}30`}}>{icon}</div>
              <div className="min-w-0">
                <div className="flex gap-2 items-center mb-1.5 flex-wrap">
                  <span className="text-[12px] font-medium text-[#e2e8f0]">{s.resource_name}</span>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded tracking-[.05em]" style={{background:`${color}20`,color}}>{s.suggestion_type.toUpperCase()}</span>
                  <span className={`text-[10px] ${s.confidence==='high' ? 'text-[#34d399]' : 'text-[#f59e0b]'}`}>
                    {s.confidence==='high' ? '● HIGH CONFIDENCE' : '◐ MEDIUM CONFIDENCE'}
                  </span>
                </div>
                <p className="text-xs text-[#475569]">{s.detail}</p>
                <p className="text-[10px] text-[#334155] mt-1">Current cost: ${s.current_cost_monthly.toFixed(2)}/mo</p>
              </div>
            </div>
            <div className="text-right shrink-0">
              <p className="text-[10px] text-[#334155] tracking-[.08em] uppercase mb-0.5">Save</p>
              <p className="text-2xl font-bold text-[#34d399]">${s.estimated_savings_monthly.toFixed(0)}</p>
              <p className="text-[10px] text-[#1e3a5f]">per month</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
