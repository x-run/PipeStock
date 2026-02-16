import { AlertTriangle } from 'lucide-react';
import type { DashboardStockItem, OthersTotalSummary } from '../types/api';

interface Props {
  items: DashboardStockItem[];
  others: OthersTotalSummary;
}

function Bar({ available, reserved, pendingReturn, onHand }: {
  available: number;
  reserved: number;
  pendingReturn: number;
  onHand: number;
  maxOnHand: number;
}) {
  if (onHand === 0) return <div className="h-6 rounded bg-gray-100" />;
  const availPct = (available / onHand) * 100;
  const reservedPct = (reserved / onHand) * 100;
  const pendingPct = (pendingReturn / onHand) * 100;
  return (
    <div className="flex h-6 rounded overflow-hidden bg-gray-100 w-full">
      <div
        className="bg-blue-500 transition-all duration-300"
        style={{ width: `${availPct}%` }}
      />
      <div
        className="bg-purple-300 transition-all duration-300"
        style={{ width: `${reservedPct}%` }}
      />
      <div
        className="bg-blue-200 transition-all duration-300"
        style={{ width: `${pendingPct}%` }}
      />
    </div>
  );
}

export default function StockBarChart({ items, others }: Props) {
  const allOnHand = [...items.map(i => i.on_hand), others.on_hand];
  const maxOnHand = Math.max(...allOnHand, 1);

  return (
    <div className="space-y-2">
      {items.map((item) => (
        <div key={item.product_id} className="flex items-center gap-3">
          <div className="w-24 shrink-0 truncate text-sm font-medium text-gray-700">
            {item.code}
          </div>
          <div className="flex-1 min-w-0" style={{ maxWidth: `${(item.on_hand / maxOnHand) * 100}%` }}>
            <Bar
              available={item.available}
              reserved={item.reserved_total - item.reserved_pending_return}
              pendingReturn={item.reserved_pending_return}
              onHand={item.on_hand}
              maxOnHand={maxOnHand}
            />
          </div>
          <div className="w-24 shrink-0 text-right text-sm tabular-nums text-gray-600">
            {item.on_hand.toLocaleString()} {item.unit}
          </div>
          <div className="w-6 shrink-0">
            {item.needs_reorder && (
              <AlertTriangle className="w-4 h-4 text-amber-500" aria-label="要発注" />
            )}
          </div>
        </div>
      ))}

      {others.on_hand > 0 && (
        <div className="flex items-center gap-3 pt-1 border-t border-gray-200">
          <div className="w-24 shrink-0 text-sm text-gray-500">その他</div>
          <div className="flex-1 min-w-0" style={{ maxWidth: `${(others.on_hand / maxOnHand) * 100}%` }}>
            <Bar
              available={others.available}
              reserved={others.reserved_total - others.reserved_pending_return}
              pendingReturn={others.reserved_pending_return}
              onHand={others.on_hand}
              maxOnHand={maxOnHand}
            />
          </div>
          <div className="w-24 shrink-0 text-right text-sm tabular-nums text-gray-500">
            {others.on_hand.toLocaleString()}
          </div>
          <div className="w-6 shrink-0" />
        </div>
      )}

      <div className="flex items-center gap-4 pt-2 text-xs text-gray-500">
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded bg-blue-500" />
          Available
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded bg-purple-300" />
          引当
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded bg-blue-200" />
          検品待ち
        </span>
      </div>
    </div>
  );
}
