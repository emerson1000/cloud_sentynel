'use client';
// src/app/dashboard/settings/page.tsx
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import toast from 'react-hot-toast';
import { createClient } from '@/lib/supabase/client';

export default function SettingsPage() {
  const router   = useRouter();
  const supabase = createClient();

  const [profile,  setProfile]  = useState({ full_name:'', email:'' });
  const [notif,    setNotif]    = useState({ threshold:15, email:true, telegram:false, chat_id:'' });
  const [saving,   setSaving]   = useState(false);
  const [loading,  setLoading]  = useState(true);

  useEffect(()=>{
    supabase.auth.getUser().then(async({data:{user}})=>{
      if (!user) return;
      const {data:p} = await supabase.from('profiles').select('*').eq('id',user.id).single();
      setProfile({full_name:p?.full_name||'',email:user.email||''});
      if (p?.notification_config) setNotif(p.notification_config);
      setLoading(false);
    });
  },[]);

  const saveProfile = async () => {
    setSaving(true);
    const {data:{user}} = await supabase.auth.getUser();
    if (!user) return;
    const {error} = await supabase.from('profiles').upsert({
      id: user.id,
      full_name: profile.full_name,
      notification_config: notif,
      updated_at: new Date().toISOString(),
    });
    setSaving(false);
    if (error) toast.error(error.message);
    else toast.success('Settings saved');
  };

  const signOut = async () => {
    await supabase.auth.signOut();
    router.push('/');
    router.refresh();
  };

  const inputCls = "w-full bg-[#03070f] border border-[#0a1628] text-[#e2e8f0] font-mono text-[13px] px-3 py-2.5 rounded-lg outline-none transition-colors focus:border-[#f59e0b]/40";
  const labelCls = "block text-[10px] text-[#475569] tracking-[.08em] uppercase mb-1.5";

  if (loading) return <div className="animate-pulse space-y-3 max-w-lg">{[...Array(3)].map((_,i)=><div key={i} className="h-28 bg-[#060d1a] rounded-xl border border-[#0d2340]"/>)}</div>;

  return (
    <div className="animate-fade-in max-w-[540px] flex flex-col gap-4">

      {/* Profile */}
      <div className="bg-[#060d1a] border border-[#0d2340] rounded-xl p-6">
        <p className="text-[10px] text-[#334155] tracking-[.1em] uppercase mb-5">Profile</p>
        <div className="flex flex-col gap-4">
          <div>
            <label className={labelCls}>Full Name</label>
            <input className={inputCls} value={profile.full_name} onChange={e=>setProfile(p=>({...p,full_name:e.target.value}))} />
          </div>
          <div>
            <label className={labelCls}>Email</label>
            <input className={inputCls} value={profile.email} disabled style={{opacity:.5,cursor:'not-allowed'}} />
            <p className="text-[10px] text-[#1e3a5f] mt-1">Email cannot be changed here. Contact support.</p>
          </div>
        </div>
        <button onClick={saveProfile} disabled={saving} className="mt-5 bg-[#f59e0b] text-[#03070f] font-mono font-medium text-xs px-5 py-2.5 rounded-lg tracking-[.06em] hover:bg-[#fbbf24] transition-colors disabled:opacity-50">
          {saving ? 'Saving...' : 'Save profile'}
        </button>
      </div>

      {/* Notifications */}
      <div className="bg-[#060d1a] border border-[#0d2340] rounded-xl p-6">
        <p className="text-[10px] text-[#334155] tracking-[.1em] uppercase mb-5">Notifications</p>
        <div className="flex flex-col gap-4">
          <div>
            <label className={labelCls}>Anomaly Threshold (%)</label>
            <input type="number" className={inputCls} value={notif.threshold} min={5} max={100}
              onChange={e=>setNotif(p=>({...p,threshold:Number(e.target.value)}))} />
            <p className="text-[10px] text-[#1e3a5f] mt-1">Alert when daily spend exceeds this % above 7-day average</p>
          </div>
          <div className="flex items-center justify-between p-3 bg-[#03070f] border border-[#0a1628] rounded-lg">
            <div>
              <p className="text-xs text-[#94a3b8]">Email alerts</p>
              <p className="text-[10px] text-[#334155]">Weekly report + anomaly notifications</p>
            </div>
            <button onClick={()=>setNotif(p=>({...p,email:!p.email}))}
              className={`w-10 h-5 rounded-full transition-colors relative ${notif.email ? 'bg-[#f59e0b]' : 'bg-[#1e293b]'}`}>
              <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-all ${notif.email ? 'left-[22px]' : 'left-0.5'}`} />
            </button>
          </div>
          <div className="flex items-center justify-between p-3 bg-[#03070f] border border-[#0a1628] rounded-lg">
            <div>
              <p className="text-xs text-[#94a3b8]">Telegram alerts</p>
              <p className="text-[10px] text-[#334155]">Instant anomaly notifications via bot</p>
            </div>
            <button onClick={()=>setNotif(p=>({...p,telegram:!p.telegram}))}
              className={`w-10 h-5 rounded-full transition-colors relative ${notif.telegram ? 'bg-[#f59e0b]' : 'bg-[#1e293b]'}`}>
              <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-all ${notif.telegram ? 'left-[22px]' : 'left-0.5'}`} />
            </button>
          </div>
          {notif.telegram && (
            <div>
              <label className={labelCls}>Telegram Chat ID</label>
              <input className={inputCls} placeholder="1234567890" value={notif.chat_id}
                onChange={e=>setNotif(p=>({...p,chat_id:e.target.value}))} />
              <p className="text-[10px] text-[#1e3a5f] mt-1">Talk to @userinfobot on Telegram to get your Chat ID</p>
            </div>
          )}
        </div>
        <button onClick={saveProfile} disabled={saving} className="mt-5 bg-[#f59e0b] text-[#03070f] font-mono font-medium text-xs px-5 py-2.5 rounded-lg tracking-[.06em] hover:bg-[#fbbf24] transition-colors disabled:opacity-50">
          {saving ? 'Saving...' : 'Save notifications'}
        </button>
      </div>

      {/* Plan */}
      <div className="bg-[#060d1a] border border-[#0d2340] rounded-xl p-6">
        <p className="text-[10px] text-[#334155] tracking-[.1em] uppercase mb-4">Current Plan</p>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-[#f1f5f9]">Scout (Free)</p>
            <p className="text-[11px] text-[#475569] mt-0.5">1 connection · Weekly report · Email alerts</p>
          </div>
          <a href="/#pricing" className="text-xs text-[#f59e0b] border border-[rgba(245,158,11,.35)] px-4 py-2 rounded-lg hover:border-[#f59e0b] hover:bg-[rgba(245,158,11,.08)] transition-all">
            Upgrade →
          </a>
        </div>
      </div>

      {/* Danger zone */}
      <div className="bg-[#0a0505] border border-[#2d0a0a] rounded-xl p-5">
        <p className="text-[10px] text-[#7f1d1d] tracking-[.1em] uppercase mb-4">Danger Zone</p>
        <button onClick={signOut} className="border border-[#7f1d1d] text-[#f87171] font-mono text-xs px-5 py-2 rounded-lg hover:bg-[#7f1d1d]/10 transition-colors">
          Sign out
        </button>
      </div>
    </div>
  );
}
