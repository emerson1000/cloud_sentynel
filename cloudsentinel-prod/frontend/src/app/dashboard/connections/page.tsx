'use client';
// src/app/dashboard/connections/page.tsx
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import toast from 'react-hot-toast';
import { api, type Connection } from '@/lib/api';
import { format } from 'date-fns';

const PROV: Record<string,{name:string,icon:string,color:string}> = {
  azure: { name:'Microsoft Azure',        icon:'☁', color:'#0078d4' },
  aws:   { name:'Amazon Web Services',    icon:'▲', color:'#ff9900' },
  gcp:   { name:'Google Cloud Platform',  icon:'◆', color:'#4285f4' },
};

export default function ConnectionsPage() {
  const router  = useRouter();
  const [conns,    setConns]    = useState<Connection[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [deleting, setDeleting] = useState<string|null>(null);

  useEffect(() => { load(); }, []);
  const load = () => api.connections.list().then(setConns).catch(()=>{}).finally(()=>setLoading(false));

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Remove "${name}"? Reports will be kept but no new scans will run.`)) return;
    setDeleting(id);
    try { await api.connections.del(id); toast.success('Connection removed'); load(); }
    catch(e:any) { toast.error(e.message); }
    finally { setDeleting(null); }
  };

  if (loading) return <div className="animate-pulse space-y-3">{[...Array(2)].map((_,i)=><div key={i} className="h-20 bg-[#060d1a] rounded-xl border border-[#0d2340]"/>)}</div>;

  return (
    <div className="animate-fade-in flex flex-col gap-3">
      <div className="flex justify-end">
        <button onClick={()=>router.push('/onboarding')} className="bg-[#f59e0b] text-[#03070f] font-mono font-medium text-xs px-4 py-2.5 rounded-lg tracking-[.07em] hover:bg-[#fbbf24] transition-colors">
          + Add Connection
        </button>
      </div>

      {conns.length === 0 ? (
        <div className="text-center py-16 text-[#334155]">
          <p className="text-4xl mb-3">🔌</p>
          <p className="text-sm mb-4">No cloud connections yet.</p>
          <button onClick={()=>router.push('/onboarding')} className="text-[#f59e0b] text-sm hover:underline">Connect your first cloud →</button>
        </div>
      ) : conns.map((c,i)=>{
        const p = PROV[c.provider] || {name:c.provider,icon:'☁',color:'#475569'};
        return (
          <div key={i} className="bg-[#060d1a] border border-[#0d2340] rounded-xl px-5 py-4 flex items-center gap-4 hover:border-[#0d2f50] transition-colors">
            <div className="w-11 h-11 rounded-xl flex items-center justify-center text-2xl shrink-0" style={{background:`${p.color}18`,border:`1px solid ${p.color}40`}}>{p.icon}</div>
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-medium text-[#f1f5f9]">{c.display_name}</p>
              <p className="text-[11px] text-[#334155] mt-0.5">
                {p.name} · {c.account_identifier} · {c.last_scan_at ? `Last scan ${format(new Date(c.last_scan_at),'MMM d, HH:mm')}` : 'Never scanned'}
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {c.is_active ? (
                <><div className="pulse-dot w-1.5 h-1.5 rounded-full bg-[#22c55e]" /><span className="text-[10px] text-[#22c55e] tracking-[.07em] uppercase">Active</span></>
              ) : (
                <span className="text-[10px] text-[#475569] tracking-[.07em] uppercase">Inactive</span>
              )}
              <button
                onClick={()=>handleDelete(c.id, c.display_name)}
                disabled={deleting===c.id}
                className="ml-3 text-[11px] text-[#475569] hover:text-[#f87171] transition-colors disabled:opacity-50 font-mono"
              >
                {deleting===c.id ? 'Removing...' : 'Remove'}
              </button>
            </div>
          </div>
        );
      })}

      <button onClick={()=>router.push('/onboarding')} className="w-full border border-dashed border-[#0d2340] rounded-xl py-5 flex items-center justify-center gap-2.5 text-[#334155] hover:border-[rgba(245,158,11,.3)] hover:text-[#f59e0b] transition-all font-mono text-xs tracking-[.06em]">
        <span className="text-lg">+</span> Connect Azure, AWS or GCP
      </button>
    </div>
  );
}
