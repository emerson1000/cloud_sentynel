'use client';
// src/components/layout/SidebarNav.tsx

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { createClient } from '@/lib/supabase/client';
import { useRouter } from 'next/navigation';

const NAV = [
  { href: '/dashboard',              icon: '📊', label: 'Overview'    },
  { href: '/dashboard/zombies',      icon: '🧟', label: 'Zombies'     },
  { href: '/dashboard/optimize',     icon: '⚡', label: 'Optimize'    },
  { href: '/dashboard/reports',      icon: '📋', label: 'Reports'     },
  { href: '/dashboard/connections',  icon: '🔌', label: 'Connections' },
  { href: '/dashboard/settings',     icon: '⚙',  label: 'Settings'   },
];

interface Props { userName: string; tier: string; }

export function SidebarNav({ userName, tier }: Props) {
  const [open, setOpen] = useState(true);
  const pathname = usePathname();
  const router   = useRouter();

  const signOut = async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push('/');
    router.refresh();
  };

  return (
    <div className={`${open ? 'w-[220px]' : 'w-[58px]'} bg-[#050a14] border-r border-[#0a1628] flex flex-col flex-shrink-0 transition-[width] duration-250 overflow-hidden`}>
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-3.5 py-4 border-b border-[#0a1628] cursor-pointer min-h-[56px]" onClick={() => setOpen(o => !o)}>
        <div className="w-7 h-7 bg-gradient-to-br from-[#f59e0b] to-[#d97706] rounded-[6px] flex items-center justify-center text-[14px] shrink-0">⚡</div>
        {open && <span className="font-display font-extrabold text-[13px] tracking-[.1em] whitespace-nowrap">CLOUD<span className="text-[#f59e0b]">SENTINEL</span></span>}
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-3 overflow-y-auto">
        {NAV.map(item => {
          const active = pathname === item.href || (item.href !== '/dashboard' && pathname.startsWith(item.href));
          return (
            <Link key={item.href} href={item.href}
              className={`flex items-center gap-2.5 w-full px-3 py-2.5 rounded-lg text-xs tracking-[.04em] transition-all mb-0.5 ${active ? 'bg-[#0d1f35] text-[#f59e0b]' : 'text-[#334155] hover:bg-[#060d1a] hover:text-[#64748b]'} ${!open ? 'justify-center' : ''}`}
            >
              <span className="text-base shrink-0">{item.icon}</span>
              {open && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* User */}
      {open && (
        <div className="px-3.5 py-3 border-t border-[#0a1628]">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#f59e0b] to-[#d97706] flex items-center justify-center text-xs font-bold text-[#03070f] shrink-0">
              {userName[0].toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="text-[11px] text-[#94a3b8] truncate">{userName}</p>
              <p className="text-[9px] text-[#1e3a5f] tracking-[.08em] uppercase">{tier} plan</p>
            </div>
            <button onClick={signOut} title="Sign out" className="ml-auto text-[#1e3a5f] hover:text-[#475569] transition-colors text-lg leading-none bg-none border-none cursor-pointer">↪</button>
          </div>
        </div>
      )}
    </div>
  );
}
