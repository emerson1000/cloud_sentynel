'use client';
// src/app/(landing)/page.tsx  — Marketing landing page
import Link from 'next/link';
import { Logo } from '@/components/ui/Logo';

const FEATURES = [
  { icon:'🧟', title:'Zombie Hunter',       desc:'Detects orphaned disks, unused IPs and idle LBs that bleed money every month.' },
  { icon:'📡', title:'Anomaly Radar',        desc:'Compares daily spend vs your 7-day baseline. Fires alerts before bills spike.' },
  { icon:'⚡', title:'RI / CUD Optimizer',   desc:'Identifies instances running 24/7 that should be on reserved or committed pricing.' },
  { icon:'☁',  title:'Multi-Cloud',          desc:'Azure, AWS and GCP in one dashboard. One report, three clouds, zero tab-switching.' },
  { icon:'📬', title:'Weekly Digest',        desc:'Every Monday: a clean email with spend, zombies found, and savings identified.' },
  { icon:'🔐', title:'Read-Only Access',     desc:'We request Cost Reader only. We never touch your infrastructure.' },
];

const PLANS = [
  { name:'Scout',    price:0,  desc:'For indie devs',  highlight:false, cta:'Start Free',         features:['1 cloud connection','Weekly report','Zombie detection','Email alerts'] },
  { name:'Operator', price:29, desc:'For startups',    highlight:true,  cta:'Start 14-day Trial', features:['5 cloud connections','Daily anomaly scan','On-demand scan','Telegram + Email','RI recommendations','API access'] },
  { name:'Command',  price:99, desc:'For agencies',    highlight:false, cta:'Contact Sales',      features:['Unlimited connections','Real-time alerts','Multi-account reports','Slack integration','Priority support','Custom thresholds'] },
];

export default function LandingPage() {
  return (
    <div className="bg-[#03070f] min-h-screen text-[#e2e8f0] font-mono overflow-x-hidden">
      {/* NAV */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-[#03070f]/85 backdrop-blur-md border-b border-[#0d2340] px-12 flex justify-between items-center h-[60px]">
        <Logo size={16} />
        <div className="flex gap-7 items-center">
          <a href="#features" className="text-[#475569] text-[13px] cursor-pointer hover:text-[#f59e0b] transition-colors tracking-[.05em]">Features</a>
          <a href="#pricing"  className="text-[#475569] text-[13px] cursor-pointer hover:text-[#f59e0b] transition-colors tracking-[.05em]">Pricing</a>
          <a href="https://github.com/emerson1000/cloud_sentynel#readme" target="_blank" className="text-[#475569] text-[13px] cursor-pointer hover:text-[#f59e0b] transition-colors tracking-[.05em]">Docs</a>
          <Link href="/auth/login"    className="text-[#94a3b8] text-[13px] hover:text-[#f59e0b] transition-colors tracking-[.05em]">Log in</Link>
          <Link href="/auth/register" className="bg-[#f59e0b] text-[#03070f] font-medium text-xs px-5 py-2.5 rounded-md tracking-[.08em] hover:bg-[#fbbf24] transition-all hover:-translate-y-px">Get Started →</Link>
        </div>
      </nav>

      {/* HERO */}
      <div className="grid-bg min-h-screen flex flex-col items-center justify-center text-center px-6 pt-[100px] pb-16 relative overflow-hidden">
        <div className="absolute top-[20%] left-[8%] w-[450px] h-[450px] bg-[radial-gradient(circle,rgba(245,158,11,.1),transparent_70%)] pointer-events-none" />
        <div className="absolute bottom-[8%] right-[5%] w-[550px] h-[550px] bg-[radial-gradient(circle,rgba(6,182,212,.07),transparent_70%)] pointer-events-none" />

        <div className="animate-fade-up bg-[rgba(245,158,11,.12)] border border-[rgba(245,158,11,.35)] text-[#f59e0b] text-[11px] tracking-[.15em] px-5 py-1.5 rounded-full mb-7">
          AZURE · AWS · GCP — UNIFIED COST INTELLIGENCE
        </div>
        <h1 className="animate-fade-up font-display font-extrabold text-[clamp(38px,6vw,68px)] leading-[1.08] mb-6 max-w-[820px]" style={{animationDelay:'.1s'}}>
          Stop paying for cloud<br /><span className="text-[#f59e0b]">resources you forgot.</span>
        </h1>
        <p className="animate-fade-up text-[16px] text-[#64748b] max-w-[520px] leading-[1.75] mb-10" style={{animationDelay:'.2s'}}>
          CloudSentinel scans your cloud accounts weekly. Finds zombie resources, detects spend anomalies, and tells you exactly where to cut.
        </p>
        <div className="animate-fade-up flex gap-3 flex-wrap justify-center" style={{animationDelay:'.3s'}}>
          <Link href="/auth/register" className="bg-[#f59e0b] text-[#03070f] font-medium text-sm px-8 py-3.5 rounded-md tracking-[.08em] hover:bg-[#fbbf24] transition-all hover:-translate-y-px hover:shadow-[0_8px_30px_rgba(245,158,11,.35)]">
            Start for free — no card needed
          </Link>
          <Link href="/dashboard" className="border border-[rgba(245,158,11,.35)] text-[#f59e0b] text-sm px-7 py-3.5 rounded-md tracking-[.06em] hover:border-[#f59e0b] hover:bg-[rgba(245,158,11,.08)] transition-all">
            See live demo →
          </Link>
        </div>

        {/* Stats */}
        <div className="animate-fade-up flex mt-16 border border-[#0d2340] rounded-xl overflow-hidden flex-wrap" style={{animationDelay:'.45s'}}>
          {[['$2.1M+','saved for customers'],['11 min','to first insight'],['3 clouds','one dashboard'],['99.9%','zero write access']].map(([n,l],i)=>(
            <div key={i} className="px-9 py-5 text-center bg-[#060d1a]" style={{borderRight:i<3?'1px solid #0d2340':'none'}}>
              <div className="font-display font-extrabold text-xl text-[#f59e0b]">{n}</div>
              <div className="text-[10px] text-[#334155] mt-1 tracking-[.06em] uppercase">{l}</div>
            </div>
          ))}
        </div>
      </div>

      {/* FEATURES */}
      <div id="features" className="max-w-[1060px] mx-auto px-6 py-20 scroll-mt-16">
        <div className="text-center mb-14">
          <p className="text-[11px] text-[#f59e0b] tracking-[.15em] uppercase mb-3">Capabilities</p>
          <h2 className="font-display font-extrabold text-[34px]">Everything you need to stop<br/>overpaying for cloud.</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {FEATURES.map((f,i) => (
            <div key={i} className="bg-[#060d1a] border border-[#0d2340] rounded-xl p-6 hover:border-[rgba(245,158,11,.4)] hover:-translate-y-1 hover:shadow-[0_12px_40px_rgba(245,158,11,.08)] transition-all">
              <div className="text-3xl mb-4">{f.icon}</div>
              <p className="font-display font-bold text-[16px] text-[#f1f5f9] mb-2">{f.title}</p>
              <p className="text-[13px] text-[#475569] leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* PRICING */}
      <div id="pricing" className="max-w-[960px] mx-auto px-6 pb-24 scroll-mt-16">
        <div className="text-center mb-14">
          <p className="text-[11px] text-[#f59e0b] tracking-[.15em] uppercase mb-3">Pricing</p>
          <h2 className="font-display font-extrabold text-[34px]">Simple. No surprises.</h2>
        </div>
        <div className="flex gap-5 flex-wrap">
          {PLANS.map((p,i)=>(
            <div key={i} className={`flex-1 min-w-[260px] bg-[#060d1a] rounded-xl p-7 border transition-all ${p.highlight ? 'border-[rgba(245,158,11,.55)] bg-[#0c180a]' : 'border-[#0d2340]'}`}>
              {p.highlight && <p className="text-[#f59e0b] text-[10px] font-bold tracking-[.15em] mb-4">★ MOST POPULAR</p>}
              <p className="font-display font-extrabold text-xl mb-1">{p.name}</p>
              <p className="text-xs text-[#475569] mb-5">{p.desc}</p>
              <div className="mb-6">
                <span className={`font-display font-extrabold text-4xl ${p.highlight ? 'text-[#f59e0b]' : 'text-[#e2e8f0]'}`}>${p.price}</span>
                <span className="text-xs text-[#475569]">/mo</span>
              </div>
              <Link href="/auth/register" className={`block w-full text-center py-3 rounded-lg font-mono text-xs tracking-[.05em] mb-6 transition-all ${p.highlight ? 'bg-[#f59e0b] text-[#03070f] hover:bg-[#fbbf24]' : 'border border-[#1e293b] text-[#94a3b8] hover:border-[#334155]'}`}>
                {p.cta}
              </Link>
              <div className="flex flex-col gap-2.5">
                {p.features.map((f,j)=>(
                  <div key={j} className="flex gap-2 items-center text-xs text-[#64748b]">
                    <span className="text-[#f59e0b] text-[10px]">✦</span>{f}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* FOOTER */}
      <div className="border-t border-[#0d2340] px-12 py-6 flex justify-between items-center flex-wrap gap-4">
        <Logo size={13} />
        <span className="text-[11px] text-[#1e3a5f]">© 2026 CloudSentinel · Read-only access · Your data stays yours.</span>
      </div>
    </div>
  );
}
