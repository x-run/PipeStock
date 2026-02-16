import { useState } from 'react';
import type { FormEvent } from 'react';
import { X } from 'lucide-react';
import type { Operation, StockListItem, Direction } from '../types/api';
import { createTransaction, createBatchTransaction } from '../api/client';

interface TransactionModalProps {
  product: StockListItem;
  operation: Operation;
  onSuccess: () => void;
  onClose: () => void;
}

const OPERATION_LABELS: Record<Operation, string> = {
  IN: '入庫',
  OUT: '出庫',
  ADJUST: '調整',
  RESERVE: '引当',
  UNRESERVE: '引当解除',
  RETURN_ARRIVAL: '返品到着 (検品前)',
  RETURN_APPROVE: '検品OK',
  RETURN_REJECT: '検品NG',
};

const OPERATION_DESCRIPTIONS: Record<Operation, string | null> = {
  IN: null,
  OUT: null,
  ADJUST: '実棚と帳簿の差異を補正します',
  RESERVE: '注文を受けて在庫を確保します (Available が減少)',
  UNRESERVE: '出荷完了などで Reserved を解放します (Available が増加)',
  RETURN_ARRIVAL: '物理在庫が増えますが、検品完了まで Reserved でロックされます',
  RETURN_APPROVE: '検品完了、在庫復帰します (Available が増加)',
  RETURN_REJECT: '検品不合格、廃棄します (物理在庫が減少)',
};

export default function TransactionModal({
  product,
  operation,
  onSuccess,
  onClose,
}: TransactionModalProps) {
  const [qty, setQty] = useState('');
  const [direction, setDirection] = useState<Direction>('INCREASE');
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const isAdjust = operation === 'ADJUST';
  const isBatch = operation === 'RETURN_ARRIVAL' || operation === 'RETURN_REJECT';

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    const qtyNum = parseInt(qty, 10);
    if (isNaN(qtyNum) || qtyNum < 1) {
      setError('数量は1以上の整数を入力してください');
      return;
    }

    if (isAdjust && !direction) {
      setError('調整の方向を選択してください');
      return;
    }

    setSubmitting(true);

    try {
      if (isBatch) {
        // Batch operations
        if (operation === 'RETURN_ARRIVAL') {
          await createBatchTransaction(product.product_id, {
            transactions: [
              { type: 'IN', qty: qtyNum, reason: 'RETURN_ARRIVED' },
              { type: 'RESERVE', qty: qtyNum, reason: 'RETURN_PENDING' },
            ],
          });
        } else if (operation === 'RETURN_REJECT') {
          await createBatchTransaction(product.product_id, {
            transactions: [
              { type: 'UNRESERVE', qty: qtyNum, reason: 'RETURN_REJECTED' },
              { type: 'OUT', qty: qtyNum, reason: 'SCRAP' },
            ],
          });
        }
      } else {
        // Single operations
        let type: 'IN' | 'OUT' | 'ADJUST' | 'RESERVE' | 'UNRESERVE';
        if (operation === 'RETURN_APPROVE') {
          type = 'UNRESERVE';
        } else {
          type = operation as 'IN' | 'OUT' | 'ADJUST' | 'RESERVE' | 'UNRESERVE';
        }

        await createTransaction(product.product_id, {
          type,
          qty: qtyNum,
          direction: isAdjust ? direction : undefined,
          reason: reason || undefined,
        });
      }

      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'エラーが発生しました');
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
            {OPERATION_LABELS[operation]} — {product.name}
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
          {/* Description */}
          {OPERATION_DESCRIPTIONS[operation] && (
            <p className="text-sm text-gray-600 bg-blue-50 p-3 rounded">
              {OPERATION_DESCRIPTIONS[operation]}
            </p>
          )}

          {/* Current Stock */}
          <div className="text-sm space-y-1">
            <div className="font-medium text-gray-700">現在在庫:</div>
            <div className="flex gap-4 text-gray-600">
              <span>
                Available: <span className="font-bold text-blue-600">{product.available.toLocaleString()}</span>
              </span>
              <span>On-hand: {product.on_hand.toLocaleString()}</span>
              <span>Reserved: {product.reserved_total.toLocaleString()}</span>
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

          {/* Direction (ADJUST only) */}
          {isAdjust && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                方向 <span className="text-red-500">*</span>
              </label>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="direction"
                    value="INCREASE"
                    checked={direction === 'INCREASE'}
                    onChange={(e) => setDirection(e.target.value as Direction)}
                    className="w-4 h-4 text-blue-600"
                  />
                  <span className="text-sm text-gray-700">増加</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="direction"
                    value="DECREASE"
                    checked={direction === 'DECREASE'}
                    onChange={(e) => setDirection(e.target.value as Direction)}
                    className="w-4 h-4 text-blue-600"
                  />
                  <span className="text-sm text-gray-700">減少</span>
                </label>
              </div>
            </div>
          )}

          {/* Reason */}
          <div>
            <label htmlFor="reason" className="block text-sm font-medium text-gray-700 mb-1">
              理由 (任意)
            </label>
            <textarea
              id="reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              maxLength={500}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              placeholder="変更理由や備考を入力..."
            />
            <div className="text-xs text-gray-400 text-right mt-1">
              {reason.length} / 500
            </div>
          </div>

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
