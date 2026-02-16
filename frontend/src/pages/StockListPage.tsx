import { useEffect, useState, useCallback } from 'react';
import { Search, ChevronLeft, ChevronRight, AlertTriangle, Plus } from 'lucide-react';
import { fetchStockList, type StockListParams } from '../api/client';
import type { StockListItem, PaginationMeta } from '../types/api';
import Spinner from '../components/Spinner';
import ErrorMessage from '../components/ErrorMessage';
import TransactionModal from '../components/TransactionModal';
import CreateProductModal from '../components/CreateProductModal';
import Toast from '../components/Toast';
import type { ToastProps } from '../components/Toast';

type SortKey = 'qty_desc' | 'qty_asc' | 'value_desc' | 'value_asc' | 'updated_desc';
const SORT_LABELS: Record<SortKey, string> = {
  qty_desc: '数量 多い順',
  qty_asc: '数量 少ない順',
  value_desc: '金額 多い順',
  value_asc: '金額 少ない順',
  updated_desc: '更新日 新しい順',
};

type TransactionType = 'IN' | 'OUT';

function extractCategory(name: string): string {
  return name.split(/[\s\u3000]+/)[0] || name;
}

export default function StockListPage() {
  const [items, setItems] = useState<StockListItem[]>([]);
  const [pagination, setPagination] = useState<PaginationMeta>({ page: 1, per_page: 20, total: 0 });
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<SortKey>('qty_desc');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modals
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<StockListItem | null>(null);
  const [selectedType, setSelectedType] = useState<TransactionType | null>(null);

  // Toast
  const [toast, setToast] = useState<Omit<ToastProps, 'onClose'> | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    const params: StockListParams = { sort, page, per_page: 20 };
    if (query) params.q = query;
    fetchStockList(params)
      .then((res) => {
        setItems(res.data);
        setPagination(res.pagination);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [query, sort, page]);

  useEffect(load, [load]);

  const totalPages = Math.max(1, Math.ceil(pagination.total / pagination.per_page));

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
  };

  const showToast = (type: 'success' | 'error', message: string) => {
    setToast({ type, message });
  };

  const handleCreateSuccess = () => {
    setShowCreateModal(false);
    load();
    showToast('success', '商品を追加しました');
  };

  const handleTransactionSuccess = () => {
    setSelectedProduct(null);
    setSelectedType(null);
    load();
    showToast('success', '在庫を更新しました');
  };

  const handleOpenTransaction = (product: StockListItem, type: TransactionType) => {
    setSelectedProduct(product);
    setSelectedType(type);
  };

  const handleCloseTransaction = () => {
    setSelectedProduct(null);
    setSelectedType(null);
  };

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-col sm:flex-row gap-3">
        <form onSubmit={handleSearch} className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="コード・商品名・仕様で検索..."
            className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </form>
        <select
          value={sort}
          onChange={(e) => { setSort(e.target.value as SortKey); setPage(1); }}
          className="text-sm border border-gray-300 rounded-lg px-3 py-2 cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {Object.entries(SORT_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors whitespace-nowrap"
        >
          <Plus className="w-4 h-4" />
          商品追加
        </button>
      </div>

      {error && <ErrorMessage message={error} onRetry={load} />}

      {/* Table */}
      <div className="rounded-xl border border-gray-200 bg-white overflow-x-auto">
        {loading ? (
          <Spinner />
        ) : items.length === 0 ? (
          <p className="text-sm text-gray-400 py-12 text-center">商品がありません</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50 text-left">
                <th className="px-4 py-3 font-medium text-gray-600">Code</th>
                <th className="px-4 py-3 font-medium text-gray-600">商品名</th>
                <th className="px-4 py-3 font-medium text-gray-600">カテゴリ</th>
                <th className="px-4 py-3 font-medium text-gray-600 text-right">On-hand</th>
                <th className="px-4 py-3 font-medium text-gray-600 text-right">Reserved</th>
                <th className="px-4 py-3 font-medium text-gray-600 text-right font-bold">Available</th>
                <th className="px-4 py-3 font-medium text-gray-600 text-right">発注点</th>
                <th className="px-4 py-3 font-medium text-gray-600 text-center">状態</th>
                <th className="px-4 py-3 font-medium text-gray-600 text-center">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.product_id}
                  className={`border-b border-gray-100 hover:bg-gray-50 transition-colors ${
                    item.needs_reorder ? 'bg-amber-50/50' : ''
                  }`}
                >
                  <td className="px-4 py-3 font-mono text-gray-700">{item.code}</td>
                  <td className="px-4 py-3 text-gray-900">{item.name}</td>
                  <td className="px-4 py-3 text-gray-500">{extractCategory(item.name)}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-gray-700">
                    {item.on_hand.toLocaleString()} {item.unit}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-gray-400">
                    {item.reserved_total.toLocaleString()}
                    {item.reserved_pending_return > 0 && (
                      <span className="ml-1 text-xs text-orange-400">
                        (検品{item.reserved_pending_return})
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums font-bold text-blue-600">
                    {item.available.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-gray-500">
                    {item.reorder_point}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {item.needs_reorder ? (
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-700 bg-amber-100 px-2 py-0.5 rounded-full">
                        <AlertTriangle className="w-3 h-3" />
                        要発注
                      </span>
                    ) : (
                      <span className="text-xs text-gray-400">正常</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleOpenTransaction(item, 'IN')}
                        className="px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                      >
                        入庫
                      </button>
                      <button
                        onClick={() => handleOpenTransaction(item, 'OUT')}
                        className="px-2 py-1 text-xs bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors"
                      >
                        出庫
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {!loading && items.length > 0 && (
        <div className="flex items-center justify-between text-sm text-gray-600">
          <span>
            {pagination.total} 件中 {(page - 1) * pagination.per_page + 1}〜
            {Math.min(page * pagination.per_page, pagination.total)} 件
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-1.5 rounded border border-gray-300 disabled:opacity-30 hover:bg-gray-100 cursor-pointer disabled:cursor-default transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="tabular-nums">{page} / {totalPages}</span>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="p-1.5 rounded border border-gray-300 disabled:opacity-30 hover:bg-gray-100 cursor-pointer disabled:cursor-default transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Create Product Modal */}
      {showCreateModal && (
        <CreateProductModal
          onSuccess={handleCreateSuccess}
          onClose={() => setShowCreateModal(false)}
        />
      )}

      {/* Transaction Modal */}
      {selectedProduct && selectedType && (
        <TransactionModal
          product={selectedProduct}
          type={selectedType}
          onSuccess={handleTransactionSuccess}
          onClose={handleCloseTransaction}
        />
      )}

      {/* Toast */}
      {toast && (
        <Toast
          type={toast.type}
          message={toast.message}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
}
