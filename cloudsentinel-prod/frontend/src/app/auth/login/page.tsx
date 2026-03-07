'use client';
// src/app/auth/login/page.tsx

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import toast from 'react-hot-toast';
import { createClient } from '@/lib/supabase/client';
import { Logo } from '@/components/ui/Logo';

export default function LoginPage() {
  const router = useRouter();
  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [loading,  setLoading]  = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
      toast.error(error.message);
      setLoading(false);
    } else {
      toast.success('Welcome back!');
      router.push('/dashboard');
      router.refresh();
    }
  };

  return (
    <div className="min-h-screen bg-[#03070f] flex font-mono text-[#e2e8f0]">
      {/* LEFT PANEL */}
      <div className="flex-1 bg-[#060d1a] border-r border-[#0d2340] p-12 hidden lg:flex flex-col justify-between">
        <Link href="/"><Logo /></Link>
        <div>
          <p className="text-[10px] text-[#334155] tracking-[.12em] uppercase mb-5">What you get</p>
          {[
            ['🧟','Zombie resource scanner','Finds unattached disks, idle IPs and empty LBs across all clouds.'],
            ['📡','Spend anomaly detection','Compares daily spend vs 7-day baseline. Fires alerts before bills spike.'],
            ['💡','RI / CUD recommendations','Identifies VMs that should be on reserved pricing with exact savings.'],
          ].map(([ic,t,d],i)=>(
            <div key={i} className="flex gap-4 mb-7 animate-fade-in" style={{animationDelay:`${i*.1+.15}s`}}>
              <span className="text-2xl shrink-0">{ic}</span>
              <div>
                <p className="font-display font-bold text-sm text-[#f1f5f9] mb-1">{t}</p>
                <p className="text-xs text-[#475569] leading-relaxed">{d}</p>
              </div>
            </div>
          ))}
        </div>
        <p className="text-[11px] text-[#1e3a5f]">Read-only access — we never modify your infrastructure.</p>
      </div>

      {/* RIGHT PANEL */}
      <div className="w-full lg:w-[460px] flex items-center justify-center p-10">
        <div className="w-full max-w-sm animate-fade-in">
          <div className="lg:hidden mb-10"><Logo /></div>
          <h2 className="font-display font-bold text-2xl text-[#f1f5f9] mb-2">Welcome back</h2>
          <p className="text-sm text-[#475569] mb-8">Sign in to your workspace.</p>

          <form onSubmit={handleLogin} className="flex flex-col gap-4">
            <div>
              <label className="block text-[10px] text-[#475569] tracking-[.08em] uppercase mb-1.5">Email</label>
              <input
                type="email" required value={email} onChange={e=>setEmail(e.target.value)}
                placeholder="ada@company.com"
                className="w-full bg-[#060d1a] border border-[#0d2340] text-[#e2e8f0] font-mono text-[13px] px-3.5 py-3 rounded-lg outline-none transition-colors focus:border-[#f59e0b]/60 placeholder:text-[#1e3a5f]"
              />
            </div>
            <div>
              <label className="block text-[10px] text-[#475569] tracking-[.08em] uppercase mb-1.5">Password</label>
              <input
                type="password" required value={password} onChange={e=>setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-[#060d1a] border border-[#0d2340] text-[#e2e8f0] font-mono text-[13px] px-3.5 py-3 rounded-lg outline-none transition-colors focus:border-[#f59e0b]/60 placeholder:text-[#1e3a5f]"
              />
            </div>
            <button
              type="submit" disabled={loading}
              className="w-full mt-2 py-3.5 bg-[#f59e0b] text-[#03070f] font-mono font-medium text-sm rounded-lg tracking-[.07em] transition-all hover:bg-[#fbbf24] disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {loading ? '⚙ Authenticating...' : 'Sign in →'}
            </button>
          </form>

          <p className="mt-5 text-center text-xs text-[#334155]">
            Don't have an account?{' '}
            <Link href="/auth/register" className="text-[#f59e0b] hover:underline">Create one free</Link>
          </p>

          <div className="mt-8 p-4 bg-[#060d1a] border border-[#0d2340] rounded-lg text-center">
            <p className="text-[10px] text-[#334155] tracking-[.1em] uppercase mb-2">Demo account</p>
            <p className="text-xs text-[#64748b] mb-3">demo@cloudsentinel.io / demo1234</p>
            <button
              onClick={()=>{setEmail('demo@cloudsentinel.io');setPassword('demo1234');}}
              className="text-[11px] text-[#64748b] border border-[#1e293b] px-4 py-1.5 rounded hover:border-[#334155] transition-colors"
            >
              Fill demo credentials
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
