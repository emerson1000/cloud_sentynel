// src/components/ui/ZombieRow.tsx
import { type OrphanResource } from '@/lib/api';

const SEV: Record<string, [string, string]> = {
  critical: ['#450a0a','#fca5a5'], high: ['#431407','#fb923c'],
  medium:   ['#422006','#fbbf24'], low:  ['#0c1a2e','#60a5fa'],
};

function getSeverity(resource: OrphanResource): string {
  if (resource.resource_type.toLowerCase().includes('virtual machine') && resource.reason.toLowerCase().includes('stopped')) return 'critical';
  if (resource.estimated_monthly_cost_usd > 50) return 'high';
  if (resource.estimated_monthly_cost_usd > 15) return 'medium';
  return 'low';
}

export function ZombieRow({ resource }: { resource: OrphanResource }) {
  const sev = getSeverity(resource);
  const [bg, color] = SEV[sev] || SEV.low;
  return (
    <div className="flex justify-between items-center px-4 py-2.5 bg-[#03070f] border border-[#0a1628] rounded-lg hover:bg-[#060d1a] transition-colors">
      <div className="min-w-0">
        <span className="text-xs font-medium text-[#e2e8f0]">{resource.name}</span>
        <span className="text-[10px] text-[#334155] ml-3">{resource.reason}</span>
      </div>
      <div className="flex gap-2.5 items-center ml-3 shrink-0">
        <span className="text-[13px] text-[#f87171] font-bold">${resource.estimated_monthly_cost_usd.toFixed(2)}/mo</span>
        <span style={{ background: bg, color, fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 4, letterSpacing: '.06em', textTransform: 'uppercase' as const }}>{sev}</span>
      </div>
    </div>
  );
}
