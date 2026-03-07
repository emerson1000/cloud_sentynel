'use client';
import { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { api } from '@/lib/api';

interface QuotaStatus {
  allowed: boolean; used: number; limit: number;
  tier: string; resets_on: string; reason?: string;
}

export function ScanButton({ onScanComplete }: { onScanComplete: () => void }) {
  const [scanning, setScanning] = useState(false);
  const [quota,    setQuota]    = useState<QuotaStatus | null>(null);

  useEffect(() => { loadQuota(); }, []);

  const loadQuota = async () => {
    try { setQuota(await api.scan.quota()); } catch {}
  };

  const run = async () => {
    if (quota && !quota.allowed) {
      toast.error(quota.reason || 'Scan limit reached. Resets next Monday.');
      return;
    }
    setScanning(true);
    try {
      const conns = await api.connections.list();
      if (!conns.length) { toast.error('No connections to scan'); return; }
      const results = await Promise.allSettled(conns.map((c: any) => api.scan.trigger(c.id)));
      const ok  = results.filter(r => r.status === 'fulfilled').length;
      const bad = results.filter(r => r.status === 'rejected').length;
      if (ok > 0)  { toast.success(`Scan complete for ${ok} connection${ok > 1 ? 's' : ''}.`); await loadQuota(); onScanComplete(); }
      if (bad > 0) { toast.error(`${bad} connection${bad > 1 ? 's' : ''} failed to scan.`); }
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (detail?.error === 'quota_exceeded') {
        toast.error(detail.message);
        setQuota(q => q ? { ...q, allowed: false } : q);
      } else {
        toast.error(err.message || 'Scan failed. Check your connection credentials.');
      }
    } finally { setScanning(false); }
  };

  const isDisabled  = scanning || (quota !== null && !quota.allowed);
  const isLimitFree = quota?.tier === 'free';

  return (
    <div className="flex flex-col items-end gap-1">
      <button onClick={run} disabled={isDisabled} title={quota?.reason || 'Run a scan now'}
        className={`font-mono font-medium text-xs px-4 py-2.5 rounded-lg tracking-[.07em] transition-all flex items-center gap-1.5
          ${isDisabled ? 'bg-[#1e293b] text-[#475569] cursor-not-allowed' : 'bg-[#f59e0b] text-[#03070f] hover:bg-[#fbbf24] hover:-translate-y-px'}`}>
        {scanning ? <><span className="animate-spin inline-block">⚙</span> Scanning...</> : isLimitFree ? '🔒 Scan Now' : '▶ Scan Now'}
      </button>
      {quota && quota.limit > 0 && (
        <p className={`text-[10px] tracking-[.05em] ${quota.allowed ? 'text-[#334155]' : 'text-[#ef4444]'}`}>
          {quota.used}/{quota.limit} this week · resets {quota.resets_on}
        </p>
      )}
      {isLimitFree && (
        <p className="text-[10px] text-[#334155]">
          <a href="/dashboard/settings" className="text-[#f59e0b] hover:underline">Upgrade</a> for on-demand scans
        </p>
      )}
    </div>
  );
}
