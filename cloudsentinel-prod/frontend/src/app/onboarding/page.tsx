'use client';
// src/app/onboarding/page.tsx

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import toast from 'react-hot-toast';
import { api } from '@/lib/api';
import { Logo } from '@/components/ui/Logo';

const PROVIDERS = {
  azure: { name:'Microsoft Azure',          icon:'☁',  color:'#0078d4', credNote:'Service Principal with Cost Management Reader + Reader roles' },
  aws:   { name:'Amazon Web Services',      icon:'▲',  color:'#ff9900', credNote:'IAM user with ReadOnlyAccess + CostExplorer permissions' },
  gcp:   { name:'Google Cloud Platform',   icon:'◆',  color:'#4285f4', credNote:'Service Account with Billing Viewer + Compute Viewer roles' },
} as const;

type Provider = keyof typeof PROVIDERS;

const STEPS = ['Choose Cloud', 'Enter Credentials', 'Verify Access', 'Done'];

export default function OnboardingPage() {
  const router = useRouter();
  const [step,    setStep]    = useState(0);
  const [provider,setProv]    = useState<Provider | null>(null);
  const [form,    setForm]    = useState({
    display_name:'', subscription_id:'', tenant_id:'', client_id:'', client_secret:'',
    aws_access_key_id:'', aws_secret_access_key:'', aws_region:'us-east-1',
    project_id:'', billing_account_id:'', service_account_json:'',
  });
  const [testing,  setTesting]  = useState(false);
  const [verified, setVerified] = useState(false);
  const [saving,   setSaving]   = useState(false);
  const f = (k: string) => (e: React.ChangeEvent<HTMLInputElement|HTMLTextAreaElement|HTMLSelectElement>) =>
    setForm(p => ({...p, [k]: e.target.value}));

  const canProceed = () => {
    if (step === 0) return !!provider;
    if (step === 1) {
      if (!form.display_name) return false;
      if (provider === 'azure') return !!(form.subscription_id && form.tenant_id && form.client_id && form.client_secret);
      if (provider === 'aws')   return !!(form.aws_access_key_id && form.aws_secret_access_key);
      if (provider === 'gcp')   return !!(form.project_id && form.billing_account_id && form.service_account_json);
    }
    return true;
  };

  const handleVerify = async () => {
    setTesting(true);
    try {
      const body: any = { provider, display_name: form.display_name };
      if (provider === 'azure') Object.assign(body, { subscription_id: form.subscription_id, tenant_id: form.tenant_id, client_id: form.client_id, client_secret: form.client_secret });
      if (provider === 'aws')   Object.assign(body, { aws_access_key_id: form.aws_access_key_id, aws_secret_access_key: form.aws_secret_access_key, aws_region: form.aws_region });
      if (provider === 'gcp')   Object.assign(body, { project_id: form.project_id, billing_account_id: form.billing_account_id, service_account_json: JSON.parse(form.service_account_json) });

      await api.connections.add(body);
      setVerified(true);
    } catch (err: any) {
      toast.error(err.message || 'Connection failed. Check your credentials.');
    } finally {
      setTesting(false);
    }
  };

  const inputCls = "w-full bg-[#060d1a] border border-[#0d2340] text-[#e2e8f0] font-mono text-[13px] px-3.5 py-2.5 rounded-lg outline-none transition-colors focus:border-[#f59e0b]/60 placeholder:text-[#1e3a5f]";
  const labelCls = "block text-[10px] text-[#475569] tracking-[.08em] uppercase mb-1.5";

  return (
    <div className="min-h-screen bg-[#03070f] font-mono text-[#e2e8f0] flex items-center justify-center p-6">
      <div className="w-full max-w-[600px]">
        {/* Header */}
        <div className="flex items-center justify-between mb-12">
          <Logo />
          <span className="text-xs text-[#334155]">You can add more clouds later →</span>
        </div>

        <h2 className="font-display font-bold text-2xl text-[#f1f5f9] mb-1.5">Connect your first cloud account</h2>
        <p className="text-sm text-[#475569] mb-8">Takes ~3 minutes. Read-only access — we never modify your infrastructure.</p>

        {/* Steps indicator */}
        <div className="flex items-center mb-10">
          {STEPS.map((s,i) => (
            <div key={i} className="flex items-center">
              <div className="flex flex-col items-center gap-1.5">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300 ${i < step ? 'bg-[#f59e0b] text-[#03070f]' : i === step ? 'bg-[#0a0f1a] border-2 border-[#f59e0b] text-[#f59e0b]' : 'bg-[#0a0f1a] border-2 border-[#1e293b] text-[#334155]'}`}>
                  {i < step ? '✓' : i + 1}
                </div>
                <span className={`text-[10px] tracking-[.07em] whitespace-nowrap ${i === step ? 'text-[#f59e0b]' : 'text-[#334155]'}`}>{s}</span>
              </div>
              {i < STEPS.length - 1 && (
                <div className={`w-14 h-0.5 mx-1 mb-4 transition-all duration-300 ${i < step ? 'bg-[#f59e0b]' : 'bg-[#1e293b]'}`} />
              )}
            </div>
          ))}
        </div>

        {/* STEP 0 — Choose provider */}
        {step === 0 && (
          <div className="animate-fade-in flex flex-col gap-3">
            <p className="text-[10px] text-[#475569] tracking-[.1em] uppercase mb-2">Select Cloud Provider</p>
            {(Object.entries(PROVIDERS) as [Provider, typeof PROVIDERS[Provider]][]).map(([id, p]) => (
              <div key={id} onClick={() => setProv(id)}
                className={`border rounded-xl p-5 cursor-pointer transition-all ${provider === id ? 'border-[#f59e0b] bg-[#0d1a08] shadow-[0_0_20px_rgba(245,158,11,.08)]' : 'border-[#0d2340] bg-[#060d1a] hover:border-[#f59e0b]/30'}`}>
                <div className="flex items-center gap-4">
                  <div className={`w-11 h-11 rounded-xl flex items-center justify-center text-2xl shrink-0`} style={{background:`${p.color}18`, border:`1px solid ${p.color}40`}}>{p.icon}</div>
                  <div>
                    <p className="font-display font-bold text-[15px] text-[#f1f5f9]">{p.name}</p>
                    <p className="text-[11px] text-[#475569] mt-0.5">{p.credNote}</p>
                  </div>
                  {provider === id && <span className="ml-auto text-[#f59e0b] text-lg">✓</span>}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* STEP 1 — Credentials */}
        {step === 1 && (
          <div className="animate-fade-in flex flex-col gap-3.5">
            <div className="flex items-center gap-3 p-3.5 bg-[#060d1a] border border-[#0d2340] rounded-lg mb-1">
              <span className="text-lg">{provider && PROVIDERS[provider].icon}</span>
              <span className="text-sm text-[#f1f5f9]">{provider && PROVIDERS[provider].name}</span>
              <button onClick={() => setStep(0)} className="ml-auto text-[11px] text-[#f59e0b] hover:underline bg-none border-none cursor-pointer font-mono">change</button>
            </div>
            <div className="p-3 bg-[#0a1f0a] border border-[#14532d]/40 rounded-lg text-xs text-[#86efac]">
              🔐 Credentials encrypted with AES-256 before storage. Read-only permissions only.
            </div>

            <div>
              <label className={labelCls}>Display Name</label>
              <input className={inputCls} placeholder="e.g. Production — Azure East US" value={form.display_name} onChange={f('display_name')} />
            </div>

            {provider === 'azure' && <>
              <div><label className={labelCls}>Subscription ID</label><input className={inputCls} placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" value={form.subscription_id} onChange={f('subscription_id')}/></div>
              <div><label className={labelCls}>Tenant ID</label><input className={inputCls} placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" value={form.tenant_id} onChange={f('tenant_id')}/></div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className={labelCls}>Client ID</label><input className={inputCls} placeholder="xxxxxxxx-xxxx-..." value={form.client_id} onChange={f('client_id')}/></div>
                <div><label className={labelCls}>Client Secret</label><input type="password" className={inputCls} placeholder="••••••••••" value={form.client_secret} onChange={f('client_secret')}/></div>
              </div>
            </>}

            {provider === 'aws' && <>
              <div><label className={labelCls}>Access Key ID</label><input className={inputCls} placeholder="AKIAIOSFODNN7EXAMPLE" value={form.aws_access_key_id} onChange={f('aws_access_key_id')}/></div>
              <div><label className={labelCls}>Secret Access Key</label><input type="password" className={inputCls} placeholder="wJalrXUtnFEMI/K7MDENG/..." value={form.aws_secret_access_key} onChange={f('aws_secret_access_key')}/></div>
              <div><label className={labelCls}>Primary Region</label>
                <select className={inputCls} value={form.aws_region} onChange={f('aws_region')}>
                  {['us-east-1','us-east-2','us-west-1','us-west-2','eu-west-1','eu-central-1','ap-southeast-1','sa-east-1'].map(r=><option key={r} value={r}>{r}</option>)}
                </select>
              </div>
            </>}

            {provider === 'gcp' && <>
              <div><label className={labelCls}>Project ID</label><input className={inputCls} placeholder="my-project-123456" value={form.project_id} onChange={f('project_id')}/></div>
              <div><label className={labelCls}>Billing Account ID</label><input className={inputCls} placeholder="XXXXXX-XXXXXX-XXXXXX" value={form.billing_account_id} onChange={f('billing_account_id')}/></div>
              <div><label className={labelCls}>Service Account JSON</label>
                <textarea className={`${inputCls} resize-y font-mono text-[11px]`} rows={5} placeholder={'{"type":"service_account","project_id":"...","private_key":"..."}'} value={form.service_account_json} onChange={f('service_account_json')}/>
              </div>
            </>}
          </div>
        )}

        {/* STEP 2 — Verify */}
        {step === 2 && (
          <div className="animate-fade-in">
            {!verified ? (
              <div className="text-center py-12">
                {testing ? (
                  <><div className="text-5xl mb-4 animate-spin-slow inline-block">⚙</div>
                    <p className="font-display font-bold text-xl text-[#f1f5f9] mb-2">Testing connection...</p>
                    <p className="text-sm text-[#475569]">Validating credentials and checking permissions.</p></>
                ) : (
                  <><div className="text-5xl mb-4">🔌</div>
                    <p className="font-display font-bold text-xl text-[#f1f5f9] mb-2">Ready to verify</p>
                    <p className="text-sm text-[#475569]">Click below to test your credentials against the cloud API.</p></>
                )}
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                <div className="text-center mb-4">
                  <div className="w-14 h-14 bg-[#0a2a0a] border-2 border-[#22c55e] rounded-full flex items-center justify-center text-2xl mx-auto mb-3 animate-check">✓</div>
                  <p className="font-display font-bold text-xl text-[#22c55e]">Connection verified!</p>
                  <p className="text-sm text-[#475569] mt-1">{form.display_name} is ready to scan.</p>
                </div>
                {['Credentials valid','Required role confirmed','Resource list access confirmed','No write permissions detected ✓'].map((t,i) => (
                  <div key={i} className="flex gap-3 items-center p-3 bg-[#060d1a] border border-[#0d2340] rounded-lg">
                    <span className="text-[#22c55e] font-bold">✓</span>
                    <span className="text-[13px] text-[#94a3b8]">{t}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* STEP 3 — Done */}
        {step === 3 && (
          <div className="animate-fade-in text-center">
            <div className="text-5xl mb-5 animate-check inline-block">🎉</div>
            <p className="font-display font-bold text-2xl text-[#f1f5f9] mb-2">You're all set!</p>
            <p className="text-sm text-[#475569] mb-8 max-w-sm mx-auto leading-relaxed">
              CloudSentinel is now scanning your {provider && PROVIDERS[provider].name}. Your first report will be ready in a few minutes.
            </p>
            <div className="grid grid-cols-2 gap-3 mb-8 text-left">
              {[['📊','Weekly reports','Every Monday 07:00 UTC'],['🚨','Anomaly alerts','If spend spikes >15%'],['🧟','Zombie scan','With every weekly report'],['💡','RI suggestions','Based on 30-day patterns']].map(([ic,t,d],i) => (
                <div key={i} className="p-4 bg-[#060d1a] border border-[#0d2340] rounded-xl">
                  <div className="text-xl mb-2">{ic}</div>
                  <p className="text-[13px] font-medium text-[#f1f5f9] mb-1">{t}</p>
                  <p className="text-[10px] text-[#334155]">{d}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-between items-center mt-8">
          <div>
            {step > 0 && step < 3 && (
              <button onClick={() => { setStep(s => s-1); setVerified(false); }} className="text-sm text-[#475569] hover:text-[#94a3b8] transition-colors bg-none border-none cursor-pointer font-mono">← Back</button>
            )}
          </div>
          <div className="flex gap-3">
            {step === 0 && <button disabled={!canProceed()} onClick={() => setStep(1)} className="bg-[#f59e0b] text-[#03070f] font-mono font-medium text-sm px-7 py-2.5 rounded-lg tracking-[.07em] transition-all hover:bg-[#fbbf24] disabled:opacity-50 disabled:cursor-not-allowed">Next →</button>}
            {step === 1 && <button disabled={!canProceed() || testing} onClick={() => { setStep(2); }} className="bg-[#f59e0b] text-[#03070f] font-mono font-medium text-sm px-7 py-2.5 rounded-lg tracking-[.07em] transition-all hover:bg-[#fbbf24] disabled:opacity-50 disabled:cursor-not-allowed">Continue →</button>}
            {step === 2 && !verified && !testing && <button onClick={handleVerify} className="bg-[#f59e0b] text-[#03070f] font-mono font-medium text-sm px-7 py-2.5 rounded-lg tracking-[.07em] hover:bg-[#fbbf24]">Test & verify →</button>}
            {step === 2 && testing && <button disabled className="bg-[#f59e0b]/60 text-[#03070f] font-mono font-medium text-sm px-7 py-2.5 rounded-lg tracking-[.07em] cursor-not-allowed">Testing...</button>}
            {step === 2 && verified && <button onClick={() => setStep(3)} className="bg-[#f59e0b] text-[#03070f] font-mono font-medium text-sm px-7 py-2.5 rounded-lg tracking-[.07em] hover:bg-[#fbbf24]">Continue →</button>}
            {step === 3 && <button disabled={saving} onClick={() => router.push('/dashboard')} className="bg-[#f59e0b] text-[#03070f] font-mono font-medium text-sm px-7 py-2.5 rounded-lg tracking-[.07em] hover:bg-[#fbbf24] disabled:opacity-50">{saving ? 'Setting up...' : 'Go to dashboard →'}</button>}
          </div>
        </div>
      </div>
    </div>
  );
}
