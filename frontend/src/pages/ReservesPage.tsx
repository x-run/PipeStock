import { useState, useEffect, useCallback } from 'react';
import { Search, Package, Lock, Unlock, Clock } from 'lucide-react';
import { fetchStockList, createTransaction } from '../api/client';
import type { StockListItem } from '../types/api';
import Toast from '../components/Toast';
import type { ToastProps } from '../components/Toast';

type ReserveType = 'RESERVE' | 'UNRESERVE';

interface ReserveTransaction {
  id: string;
  product_name: string;
  type: ReserveType;
  qty: number;
  created_at: string;
}

// Format number with thousand separators
function formatNumber(value: number): string {
  return value.toLocaleString('ja-JP');
}

// Parse formatted number string to number
function parseFormattedNumber(value: string): number | null {
  const cleaned = value.replace(/,/g, '').trim();
  if (!cleaned) return null;
  const num = parseInt(cleaned, 10);
  return isNaN(num) ? null : num;
}

export default function ReservesPage() {
  // Form state
  const [operationType, setOperationType] = useState<ReserveType>('RESERVE');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedProduct, setSelectedProduct] = useState<StockListItem | null>(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const [qty, setQty] = useState('');

  // Search results
  const [searchResults, setSearchResults] = useState<StockListItem[]>([]);
  const [searching, setSearching] = useState(false);

  // Recent transactions
  const [recentTransactions, setRecentTransactions] = useState<ReserveTransaction[]>([]);

  // UI state
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<Omit<ToastProps, 'onClose'> | null>(null);

  // Search products
  const searchProducts = useCallback(async (query: string) => {
    if (!query.trim()) {
      setSearchResults([]);
      return;
    }

    setSearching(true);
    try {
      const result = await fetchStockList({ q: query, per_page: 10 });
      setSearchResults(result.data);
    } catch (err) {
      console.error('Search error:', err);
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  }, []);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      searchProducts(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, searchProducts]);

  const handleSelectProduct = (product: StockListItem) => {
    setSelectedProduct(product);
    setSearchQuery(product.name);
    setShowDropdown(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!selectedProduct) {
      setError('商品を選択してください');
      return;
    }

    const qtyNum = parseFormattedNumber(qty);
    if (qtyNum === null || qtyNum < 1) {
      setError('数量は1以上の整数を入力してください');
      return;
    }

    setSubmitting(true);

    try {
      await createTransaction(selectedProduct.product_id, {
        type: operationType,
        qty: qtyNum,
        reason: operationType === 'RESERVE' ? 'ORDER_RECEIVED' : 'ORDER_SHIPPED',
      });

      // Add to recent transactions
      const newTransaction: ReserveTransaction = {
        id: Date.now().toString(),
        product_name: selectedProduct.name,
        type: operationType,
        qty: qtyNum,
        created_at: new Date().toISOString(),
      };
      setRecentTransactions((prev) => [newTransaction, ...prev].slice(0, 10));

      // Reset form
      setSelectedProduct(null);
      setSearchQuery('');
      setQty('');

      // Show success toast
      setToast({ type: 'success', message: '引当を更新しました' });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'エラーが発生しました';
      if (message.includes('409') || message.includes('insufficient')) {
        setError('利用可能な在庫が足りません');
      } else {
        setError(message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const getPreviewChange = (): { available: { from: number; to: number }; reserved: { from: number; to: number } } | null => {
    if (!selectedProduct || !qty) return null;
    const qtyNum = parseFormattedNumber(qty);
    if (qtyNum === null) return null;

    const availableFrom = selectedProduct.available;
    const reservedFrom = selectedProduct.reserved_total;

    if (operationType === 'RESERVE') {
      return {
        available: { from: availableFrom, to: availableFrom - qtyNum },
        reserved: { from: reservedFrom, to: reservedFrom + qtyNum },
      };
    } else {
      return {
        available: { from: availableFrom, to: availableFrom + qtyNum },
        reserved: { from: reservedFrom, to: reservedFrom - qtyNum },
      };
    }
  };

  const previewChange = getPreviewChange();

  return (
    <div className="flex gap-6 h-[calc(100vh-8rem)]">
      {/* Main Form Area */}
      <div className="flex-1 bg-white rounded-xl border border-gray-200 p-6 overflow-y-auto">
        <div className="max-w-2xl">
          <h1 className="text-2xl font-bold text-gray-900 mb-6">引当管理</h1>

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Operation Type */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">
                操作タイプ <span className="text-red-500">*</span>
              </label>
              <div className="flex gap-4">
                <label className="flex items-center gap-3 px-4 py-3 border-2 rounded-lg cursor-pointer transition-all hover:bg-purple-50 flex-1">
                  <input
                    type="radio"
                    name="type"
                    value="RESERVE"
                    checked={operationType === 'RESERVE'}
                    onChange={(e) => setOperationType(e.target.value as ReserveType)}
                    className="w-5 h-5 text-purple-600"
                  />
                  <div className="flex items-center gap-2">
                    <Lock className="w-5 h-5 text-purple-600" />
                    <div>
                      <div className="font-medium text-gray-900">引当</div>
                      <div className="text-xs text-gray-500">注文受付で在庫確保</div>
                    </div>
                  </div>
                </label>

                <label className="flex items-center gap-3 px-4 py-3 border-2 rounded-lg cursor-pointer transition-all hover:bg-green-50 flex-1">
                  <input
                    type="radio"
                    name="type"
                    value="UNRESERVE"
                    checked={operationType === 'UNRESERVE'}
                    onChange={(e) => setOperationType(e.target.value as ReserveType)}
                    className="w-5 h-5 text-green-600"
                  />
                  <div className="flex items-center gap-2">
                    <Unlock className="w-5 h-5 text-green-600" />
                    <div>
                      <div className="font-medium text-gray-900">引当解除</div>
                      <div className="text-xs text-gray-500">出荷完了で解放</div>
                    </div>
                  </div>
                </label>
              </div>
            </div>

            {/* Product Search */}
            <div className="relative">
              <label htmlFor="product" className="block text-sm font-medium text-gray-700 mb-2">
                商品 <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  id="product"
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    setShowDropdown(true);
                  }}
                  onFocus={() => setShowDropdown(true)}
                  className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                  placeholder="商品名またはコードで検索..."
                />
              </div>

              {/* Search Dropdown */}
              {showDropdown && searchQuery && (
                <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-64 overflow-y-auto">
                  {searching ? (
                    <div className="p-4 text-center text-gray-500">検索中...</div>
                  ) : searchResults.length === 0 ? (
                    <div className="p-4 text-center text-gray-500">商品が見つかりません</div>
                  ) : (
                    searchResults.map((product) => (
                      <button
                        key={product.product_id}
                        type="button"
                        onClick={() => handleSelectProduct(product)}
                        className="w-full px-4 py-3 text-left hover:bg-gray-50 border-b border-gray-100 last:border-b-0"
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="font-medium text-gray-900">{product.name}</div>
                            <div className="text-sm text-gray-500">コード: {product.code}</div>
                          </div>
                          <div className="text-right">
                            <div className="text-sm text-gray-600">
                              Available: <span className="font-bold text-blue-600">{product.available}</span>
                            </div>
                            <div className="text-xs text-gray-400">
                              Reserved: {product.reserved_total}
                            </div>
                          </div>
                        </div>
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>

            {/* Selected Product Info */}
            {selectedProduct && (
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                <div className="flex items-center gap-3">
                  <Package className="w-5 h-5 text-purple-600" />
                  <div className="flex-1">
                    <div className="font-medium text-gray-900">{selectedProduct.name}</div>
                    <div className="text-sm text-gray-600 mt-1">
                      現在在庫: Available <span className="font-bold text-blue-600">{selectedProduct.available}</span> {selectedProduct.unit} /
                      Reserved <span className="font-bold text-gray-500">{selectedProduct.reserved_total}</span> {selectedProduct.unit}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Quantity */}
            <div>
              <label htmlFor="qty" className="block text-sm font-medium text-gray-700 mb-2">
                数量 <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <input
                  type="text"
                  id="qty"
                  value={qty}
                  onChange={(e) => setQty(e.target.value)}
                  onBlur={() => {
                    const parsed = parseFormattedNumber(qty);
                    if (parsed !== null && parsed > 0) {
                      setQty(formatNumber(parsed));
                    }
                  }}
                  className="w-full px-4 py-3 pr-12 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                  placeholder="例: 10"
                  inputMode="numeric"
                />
                {selectedProduct && (
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-gray-500 pointer-events-none">
                    {selectedProduct.unit}
                  </span>
                )}
              </div>
            </div>

            {/* Info Note */}
            <div className="text-sm text-gray-600 bg-gray-50 px-4 py-3 rounded-lg">
              {operationType === 'RESERVE' ? (
                <span>💡 引当を実行すると、Availableが減少し、Reservedが増加します</span>
              ) : (
                <span>💡 引当解除を実行すると、Reservedが減少し、Availableが増加します</span>
              )}
            </div>

            {/* Error */}
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                {error}
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={submitting || !selectedProduct || !qty}
              className={`w-full px-6 py-3 text-white font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                operationType === 'RESERVE'
                  ? 'bg-purple-600 hover:bg-purple-700'
                  : 'bg-green-600 hover:bg-green-700'
              }`}
            >
              {submitting ? '実行中...' : operationType === 'RESERVE' ? '引当を実行' : '引当解除を実行'}
            </button>
          </form>
        </div>
      </div>

      {/* Sidebar - Hidden on mobile, visible on lg+ screens */}
      <div className="hidden lg:block w-80 space-y-4 overflow-y-auto">
        {/* Preview */}
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">操作プレビュー</h2>
          {previewChange ? (
            <div className="space-y-3">
              <div>
                <div className="text-xs text-gray-500 mb-1">Available:</div>
                <div className="flex items-center gap-2">
                  <span className="text-base font-bold text-gray-700">{previewChange.available.from}</span>
                  <span className="text-gray-400">→</span>
                  <span
                    className={`text-lg font-bold ${
                      previewChange.available.to >= previewChange.available.from ? 'text-green-600' : 'text-orange-600'
                    }`}
                  >
                    {previewChange.available.to}
                  </span>
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">Reserved:</div>
                <div className="flex items-center gap-2">
                  <span className="text-base font-bold text-gray-400">{previewChange.reserved.from}</span>
                  <span className="text-gray-400">→</span>
                  <span className="text-lg font-bold text-gray-600">
                    {previewChange.reserved.to}
                  </span>
                </div>
              </div>
              {previewChange.available.to < 0 && (
                <div className="text-xs text-red-600 mt-2 bg-red-50 px-2 py-1 rounded">
                  ⚠️ Availableが不足します
                </div>
              )}
            </div>
          ) : (
            <div className="text-sm text-gray-400">商品と数量を入力してください</div>
          )}
        </div>

        {/* Recent Transactions */}
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-2 mb-3">
            <Clock className="w-4 h-4 text-gray-600" />
            <h2 className="text-sm font-semibold text-gray-700">最近の操作</h2>
          </div>
          {recentTransactions.length === 0 ? (
            <div className="text-sm text-gray-400">まだ操作がありません</div>
          ) : (
            <div className="space-y-2">
              {recentTransactions.map((tx) => (
                <div key={tx.id} className="text-sm border-b border-gray-100 pb-2 last:border-b-0">
                  <div className="flex items-center justify-between mb-1">
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-medium ${
                        tx.type === 'RESERVE' ? 'bg-purple-100 text-purple-700' : 'bg-green-100 text-green-700'
                      }`}
                    >
                      {tx.type === 'RESERVE' ? '引当' : '解除'}
                    </span>
                    <span className="text-xs text-gray-500">
                      {new Date(tx.created_at).toLocaleTimeString('ja-JP', {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  </div>
                  <div className="text-gray-900 font-medium truncate">{tx.product_name}</div>
                  <div className="text-gray-600">
                    {tx.type === 'RESERVE' ? '+' : '-'}{tx.qty}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Toast */}
      {toast && <Toast type={toast.type} message={toast.message} onClose={() => setToast(null)} />}
    </div>
  );
}
