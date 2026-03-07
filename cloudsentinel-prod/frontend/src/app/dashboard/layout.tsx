// src/app/dashboard/layout.tsx
import { redirect } from 'next/navigation';
import { createClient } from '@/lib/supabase/server';
import { SidebarNav } from '@/components/layout/SidebarNav';
import { TopBar } from '@/components/layout/TopBar';

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();

  if (!user) redirect('/auth/login');

  // Get profile info
  const { data: profile } = await supabase
    .from('profiles')
    .select('full_name, tier')
    .eq('id', user.id)
    .single();

  const displayName = profile?.full_name || user.email?.split('@')[0] || 'Operator';
  const tier        = profile?.tier || 'free';

  return (
    <div className="h-screen bg-[#03070f] flex overflow-hidden font-mono text-[#e2e8f0]">
      <SidebarNav userName={displayName} tier={tier} />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <TopBar userName={displayName} />
        <main className="flex-1 overflow-y-auto p-5">
          {children}
        </main>
      </div>
    </div>
  );
}
