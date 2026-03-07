'use client';
// src/app/auth/register/page.tsx

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import toast from 'react-hot-toast';
import { createClient } from '@/lib/supabase/client';
import { Logo } from '@/components/ui/Logo';

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({ name:'', email:'', password:'', confirm:'' });
  const [loading, setLoading] = useState(false);
  const f = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) => setForm(p=>({...p,[k]:e.target.value}));

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (form.password !== form.confirm) { toast.error("Passwords don't match"); return; }
    if (form.password.length < 6)       { toast.error("Password must be at least 6 characters"); return; }

    setLoading(true);
    const supabase = createClient();

    const { data, error } = await supabase.auth.signUp({
      email: form.email,
      password: form.password,
      options: {
        data: { full_name: form.name },
        emailRedirectTo: `${location.origin}/auth/callback`,
      },
    });

    if (error) {
      toast.error(error.message);
      setLoading(false);
      return;
    }

    // If email confirmation is disabled in Supabase → user is immediately active
    if (data.session) {
      toast.success('Account created! Setting up your workspace...');
      router.push('/onboarding');
    } else {
      toast.success('Check your email to confirm your account!');
      router.push('/auth/login?message=check_email');
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-[#03070f] flex font-mono text-[#e2e8f0]">
      {/* LEFT */}
      <div className="flex-1 bg-[#060d1a] border-r border-[#0d2340] p-12 hidden lg:flex flex-col justify-between">
        <Link href="/"><Logo /></Link>
        <div>
          <p className="text-[10px] text-[#334155] tracking-[.12em] uppercase mb-5">Start for free</p>
          {[
            ['✦','No credit card required','Start with 1 cloud connection on the free plan forever.'],
            ['✦','Setup in 3 minutes','Connect your cloud account with read-only credentials.'],
            ['✦','First report in minutes','We scan immediately after you connect.'],
          ].map(([ic,t,d],i)=>(
            <div key={i} className="flex gap-4 mb-7" style={{animation:`fadeIn .5s ${i*.1+.15}s both`}}>
              <span className="text-[#f59e0b] text-sm mt-0.5 shrink-0">{ic}</span>
              <div>
                <p className="font-display font-bold text-sm text-[#f1f5f9] mb-1">{t}</p>
                <p className="text-xs text-[#475569] leading-relaxed">{d}</p>
              </div>
            </div>
          ))}
        </div>
        <p className="text-[11px] text-[#1e3a5f]">Read-only access — we never modify your infrastructure.</p>
      </div>

      {/* RIGHT */}
      <div className="w-full lg:w-[460px] flex items-center justify-center p-10">
        <div className="w-full max-w-sm animate-fade-in">
          <div className="lg:hidden mb-10"><Logo /></div>
          <h2 className="font-display font-bold text-2xl text-[#f1f5f9] mb-2">Create your account</h2>
          <p className="text-sm text-[#475569] mb-8">Free plan — no credit card required.</p>

          <form onSubmit={handleRegister} className="flex flex-col gap-4">
            {[
              ['Full Name', 'name', 'text', 'Ada Lovelace'],
              ['Email',     'email','email','ada@company.com'],
              ['Password',  'password','password','••••••••'],
              ['Confirm Password','confirm','password','••••••••'],
            ].map(([label, key, type, ph])=>(
              <div key={key}>
                <label className="block text-[10px] text-[#475569] tracking-[.08em] uppercase mb-1.5">{label}</label>
                <input
                  type={type} required={key!=='name'} placeholder={ph}
                  value={(form as any)[key]} onChange={f(key)}
                  className="w-full bg-[#060d1a] border border-[#0d2340] text-[#e2e8f0] font-mono text-[13px] px-3.5 py-3 rounded-lg outline-none transition-colors focus:border-[#f59e0b]/60 placeholder:text-[#1e3a5f]"
                />
              </div>
            ))}
            <button
              type="submit" disabled={loading}
              className="w-full mt-2 py-3.5 bg-[#f59e0b] text-[#03070f] font-mono font-medium text-sm rounded-lg tracking-[.07em] transition-all hover:bg-[#fbbf24] disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {loading ? '⚙ Creating account...' : 'Create account →'}
            </button>
          </form>

          <p className="mt-5 text-center text-xs text-[#334155]">
            Already have an account?{' '}
            <Link href="/auth/login" className="text-[#f59e0b] hover:underline">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
