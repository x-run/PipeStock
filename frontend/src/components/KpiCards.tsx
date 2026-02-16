import { Package, AlertTriangle, Clock } from 'lucide-react';
import type { DashboardStockItem } from '../types/api';

interface Props {
  items: DashboardStockItem[];
  totalItemCount: number;
}

export default function KpiCards({ items, totalItemCount }: Props) {
  const needsReorderCount = items.filter(i => i.needs_reorder).length;
  const pendingReturnCount = items.reduce(
    (sum, i) => sum + i.reserved_pending_return, 0,
  );

  const cards = [
    {
      label: '総商品数',
      value: totalItemCount,
      icon: Package,
      color: 'text-blue-600',
      bg: 'bg-blue-50',
    },
    {
      label: '要発注',
      value: needsReorderCount,
      icon: AlertTriangle,
      color: needsReorderCount > 0 ? 'text-amber-600' : 'text-gray-400',
      bg: needsReorderCount > 0 ? 'bg-amber-50' : 'bg-gray-50',
    },
    {
      label: '返品検品待ち',
      value: `${pendingReturnCount} 個`,
      icon: Clock,
      color: pendingReturnCount > 0 ? 'text-orange-600' : 'text-gray-400',
      bg: pendingReturnCount > 0 ? 'bg-orange-50' : 'bg-gray-50',
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {cards.map((c) => (
        <div
          key={c.label}
          className="rounded-xl border border-gray-200 bg-white p-4 flex items-center gap-4"
        >
          <div className={`rounded-lg ${c.bg} p-2.5`}>
            <c.icon className={`w-5 h-5 ${c.color}`} />
          </div>
          <div>
            <p className="text-sm text-gray-500">{c.label}</p>
            <p className="text-xl font-bold text-gray-900">{c.value}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
