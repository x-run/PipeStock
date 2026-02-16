import { useState } from 'react';
import type { FormEvent } from 'react';
import { X } from 'lucide-react';
import type { StockListItem } from '../types/api';
import { createTransaction } from '../api/client';

type TransactionType = 'IN' | 'OUT';

interface TransactionModalProps {
  product: StockListItem;
  type: TransactionType;
  onSuccess: () => void;
  onClose: () => void;
}

const TYPE_LABELS: Record<TransactionType, string> = {
  IN: '入庫',
  OUT: '出庫',
};

const OUT_REASONS = [
  { value: 'SHIP', label: '出荷' },
  { value: 'MOVE', label: '移動' },
  { value: 'SCRAP', label: '廃棄' },
  { value: 'SAMPLE', label: 'サンプル' },
  { value: 'OTHER', label: 'その他' },
];

export default function TransactionModal({
  product,
  type,
  onSuccess,
  onClose,
}: TransactionModalProps) {
  const [qty, setQty] = useState('');
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    const qtyNum = parseInt(qty, 10);
    if (isNaN(qtyNum) || qtyNum < 1) {
      setError('数量は1以上の整数を入力してください');
      return;
    }

    // OUT operation requires reason
    if (type === 'OUT' && !reason) {
      setError('用途を選択してください');
      return;
    }

    setSubmitting(true);

    try {
      await createTransaction(product.product_id, {
        type,
        qty: qtyNum,
        reason: type === 'IN' ? 'PURCHASE' : reason,
      });
      onSuccess();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'エラーが発生しました';
      // 409 Conflict (insufficient stock) handling
      if (message.includes('409') || message.includes('insufficient')) {
        setError('在庫が足りません');
      } else {
        setError(message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            {TYPE_LABELS[type]} — {product.name}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* Current Stock */}
          <div className="text-sm space-y-1">
            <div className="font-medium text-gray-700">現在在庫:</div>
            <div className="flex gap-4 text-gray-600">
              <span>
                Available: <span className="font-bold text-blue-600">{product.available.toLocaleString()}</span>
              </span>
              <span>On-hand: {product.on_hand.toLocaleString()}</span>
            </div>
          </div>

          {/* Quantity */}
          <div>
            <label htmlFor="qty" className="block text-sm font-medium text-gray-700 mb-1">
              数量 <span className="text-red-500">*</span>
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                id="qty"
                value={qty}
                onChange={(e) => setQty(e.target.value)}
                min="1"
                step="1"
                required
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="1"
              />
              <span className="text-sm text-gray-600">{product.unit}</span>
            </div>
          </div>

          {/* Reason (OUT only) */}
          {type === 'OUT' && (
            <div>
              <label htmlFor="reason" className="block text-sm font-medium text-gray-700 mb-1">
                用途 <span className="text-red-500">*</span>
              </label>
              <select
                id="reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">選択してください</option>
                {OUT_REASONS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* IN note */}
          {type === 'IN' && (
            <div className="text-xs text-gray-500 bg-blue-50 px-3 py-2 rounded">
              入庫理由は「PURCHASE (仕入)」として記録されます
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded text-sm">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              キャンセル
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="flex-1 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? '実行中...' : '実行'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
