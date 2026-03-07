'use client';
// src/components/ui/ScanButton.tsx
import { useState } from 'react';
import toast from 'react-hot-toast';
import { api } from '@/lib/api';

export function ScanButton({ onScanComplete }: { onScanComplete: () => void }) {
  const [scanning, setScanning] = useState(false);

  const run = async () => {
    setScanning(true);
    try {
      const conns = await api.connections.list();
      if (!conns.length) { toast.error('No connections to scan'); return; }
      const result = await api.scan.trigger(conns[0].id);
      toast.success(`Scan complete! Found $${result.report.report_data.total_potential_savings.toFixed(0)} in potential savings.`);
      onScanComplete();
    } catch (err: any) {
      if (err.message?.includes('Pro tier')) {
        toast.error('On-demand scans require the Operator plan.');
      } else {
        toast.error(err.message || 'Scan failed');
      }
    } finally {
      setScanning(false);
    }
  };

  return (
    <button onClick={run} disabled={scanning}
      className="bg-[#f59e0b] text-[#03070f] font-mono font-medium text-xs px-4 py-2.5 rounded-lg tracking-[.07em] transition-all hover:bg-[#fbbf24] disabled:opacity-60 disabled:cursor-not-allowed flex items-center gap-1.5">
      {scanning ? <><span className="animate-spin-slow inline-block">⚙</span> Scanning...</> : '▶ Scan Now'}
    </button>
  );
}
