import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import type { CategoryBreakdownItem } from '../types/api';

const COLORS = [
  '#2563eb', '#7c3aed', '#0891b2', '#059669', '#d97706',
  '#dc2626', '#4f46e5', '#0d9488', '#ca8a04', '#be185d',
  '#6b7280',
];

interface Props {
  breakdown: CategoryBreakdownItem[];
  total: number;
  metric: string;
}

function formatValue(value: number, metric: string): string {
  if (metric === 'value') {
    return `\u00A5${value.toLocaleString()}`;
  }
  return value.toLocaleString();
}

export default function CategoryPieChart({ breakdown, total, metric }: Props) {
  const data = breakdown.map((b) => ({
    name: b.label,
    value: b.metric_value,
  }));

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-56 h-56">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={90}
              dataKey="value"
              stroke="none"
            >
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value) => formatValue(Number(value), metric)}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span className="text-xs text-gray-500">合計</span>
          <span className="text-lg font-bold text-gray-900">
            {formatValue(total, metric)}
          </span>
        </div>
      </div>

      <ul className="mt-4 space-y-1 w-full">
        {breakdown.map((b, i) => (
          <li key={b.key} className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2">
              <span
                className="inline-block w-3 h-3 rounded-full shrink-0"
                style={{ backgroundColor: COLORS[i % COLORS.length] }}
              />
              <span className="truncate text-gray-700">{b.label}</span>
            </span>
            <span className="ml-2 tabular-nums text-gray-600 shrink-0">
              {formatValue(b.metric_value, metric)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
