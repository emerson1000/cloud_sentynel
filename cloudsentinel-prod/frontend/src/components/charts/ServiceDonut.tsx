'use client';
// src/components/charts/ServiceDonut.tsx
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';

const COLORS = ['#f59e0b','#06b6d4','#a78bfa','#34d399','#f97316','#60a5fa','#6b7280'];

interface Service { service: string; total_cost: number; percentage: number; }

export function ServiceDonut({ data }: { data: Service[] }) {
  return (
    <div className="flex gap-4 items-center">
      <ResponsiveContainer width={110} height={110}>
        <PieChart>
          <Pie data={data} cx={50} cy={50} innerRadius={30} outerRadius={50}
            dataKey="total_cost" paddingAngle={1}>
            {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} opacity={0.88} />)}
          </Pie>
          <Tooltip
            contentStyle={{ background: '#060d1a', border: '1px solid #0d2340', borderRadius: 8, fontSize: 11, fontFamily: 'var(--font-mono)' }}
            formatter={(v: number) => [`$${v.toFixed(2)}`, 'Cost']}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="flex flex-col gap-1.5 flex-1 min-w-0">
        {data.slice(0, 5).map((d, i) => (
          <div key={i} className="flex justify-between items-center gap-2">
            <div className="flex items-center gap-1.5 min-w-0">
              <div className="w-2 h-2 rounded-[2px] shrink-0" style={{ background: COLORS[i] }} />
              <span className="text-[10px] text-[#475569] truncate">{d.service.split(' ')[0]}</span>
            </div>
            <span className="text-[10px] text-[#94a3b8] shrink-0">{d.percentage}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
