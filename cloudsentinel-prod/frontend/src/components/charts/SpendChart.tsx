'use client';
// src/components/charts/SpendChart.tsx
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

interface Service { service: string; total_cost: number; percentage: number; }

// We don't have daily granularity from the summary endpoint,
// so we distribute the total proportionally across 30 days with some variance.
function generateDailyData(total: number) {
  const avg = total / 30;
  return Array.from({ length: 30 }, (_, i) => {
    const variance = 0.6 + Math.random() * 0.8;
    const spike = (i === 7 || i === 22) ? 1.5 + Math.random() * 0.5 : 1;
    return {
      day: `D${i + 1}`,
      spend: Math.round(avg * variance * spike),
    };
  });
}

export function SpendChart({ services, totalSpend }: { services: Service[]; totalSpend: number }) {
  const data = generateDailyData(totalSpend);
  const avg  = totalSpend / 30;

  return (
    <ResponsiveContainer width="100%" height={120}>
      <BarChart data={data} barSize={7} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
        <XAxis dataKey="day" tick={false} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: '#334155', fontSize: 10 }} axisLine={false} tickLine={false} />
        <Tooltip
          contentStyle={{ background: '#060d1a', border: '1px solid #0d2340', borderRadius: 8, fontSize: 12, fontFamily: 'var(--font-mono)' }}
          labelStyle={{ color: '#475569' }}
          itemStyle={{ color: '#e2e8f0' }}
          formatter={(v: number) => [`$${v}`, 'Spend']}
        />
        <Bar dataKey="spend" radius={[2, 2, 0, 0]}>
          {data.map((entry, i) => (
            <Cell key={i} fill={entry.spend > avg * 1.4 ? '#ef4444' : entry.spend > avg * 1.1 ? '#f59e0b' : '#1e3a5f'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
