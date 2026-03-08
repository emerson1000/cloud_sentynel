import { SidebarNav } from '@/components/layout/SidebarNav';
import { TopBar }     from '@/components/layout/TopBar';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-screen bg-[#03070f] flex flex-col md:flex-row overflow-hidden font-mono text-[#e2e8f0]">
      <SidebarNav userName="Operator" tier="free" />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0 pt-[56px] md:pt-0">
        <TopBar userName="Operator" />
        <main className="flex-1 overflow-y-auto p-4 md:p-5">
          {children}
        </main>
      </div>
    </div>
  );
}
