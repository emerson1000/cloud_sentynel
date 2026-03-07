'use client';
// src/components/layout/TopBar.tsx
import { usePathname } from 'next/navigation';

const TITLES: Record<string, string> = {
  '/dashboard':             'Dashboard — Last 30 days',
  '/dashboard/zombies':     'Zombie Resources — Active threats',
  '/dashboard/optimize':    'Optimization Opportunities',
  '/dashboard/reports':     'Report History',
  '/dashboard/connections': 'Cloud Connections',
  '/dashboard/settings':    'Account Settings',
};

export function TopBar({ userName }: { userName: string }) {
  const pathname = usePathname();
  const title = TITLES[pathname] ?? 'Dashboard';

  return (
    <div className="h-14 border-b border-[#0a1628] flex items-center px-5 gap-4 bg-[#050a14] shrink-0">
      <span className="text-xs text-[#334155] tracking-[.04em] flex-1">{title}</span>
      <div className="flex items-center gap-2">
        <div className="pulse-dot w-1.5 h-1.5 rounded-full bg-[#22c55e]" />
        <span className="text-[10px] text-[#22c55e] tracking-[.08em] uppercase">Live</span>
      </div>
    </div>
  );
}
