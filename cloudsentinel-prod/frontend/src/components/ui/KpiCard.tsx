// src/components/ui/KpiCard.tsx
interface Props { icon: string; label: string; value: string | number; sub: string; color?: string; }
export function KpiCard({ icon, label, value, sub, color = 'text-[#e2e8f0]' }: Props) {
  return (
    <div className="bg-[#060d1a] border border-[#0d2340] rounded-xl px-5 py-4 hover:border-[#0d2f50] transition-colors">
      <div className="flex justify-between items-start mb-3">
        <span className="text-[10px] text-[#334155] tracking-[.1em] uppercase">{label}</span>
        <span className="text-lg">{icon}</span>
      </div>
      <div className={`text-2xl font-bold tracking-tight mb-1 ${color}`}>{value}</div>
      <div className="text-[10px] text-[#1e3a5f]">{sub}</div>
    </div>
  );
}
