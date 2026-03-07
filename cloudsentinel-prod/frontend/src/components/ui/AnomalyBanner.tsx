// src/components/ui/AnomalyBanner.tsx
interface Anomaly { delta_pct: number; yesterday_spend: number; avg_7day_spend: number; severity: string; }
export function AnomalyBanner({ anomaly, onDismiss }: { anomaly: Anomaly; onDismiss: () => void }) {
  return (
    <div className="bg-[#1a0505] border border-[#7f1d1d] border-l-[3px] border-l-[#ef4444] rounded-lg px-5 py-3 flex justify-between items-center gap-3">
      <div className="flex gap-3 items-center">
        <span>🚨</span>
        <span className="text-xs text-[#f87171]">
          Spending anomaly detected — yesterday's spend was <strong>${anomaly.yesterday_spend.toFixed(2)}</strong>,
          which is <strong>+{anomaly.delta_pct}%</strong> above your 7-day average of ${anomaly.avg_7day_spend.toFixed(2)}/day
        </span>
      </div>
      <button onClick={onDismiss} className="text-[#7f1d1d] hover:text-[#fca5a5] text-xl leading-none bg-none border-none cursor-pointer shrink-0">×</button>
    </div>
  );
}
