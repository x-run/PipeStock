import { useState } from 'react';
import type { FormEvent } from 'react';
import { X } from 'lucide-react';
import { createProduct } from '../api/client';
import type { CreateProductRequest } from '../types/api';

interface CreateProductModalProps {
  onSuccess: () => void;
  onClose: () => void;
}

export default function CreateProductModal({ onSuccess, onClose }: CreateProductModalProps) {
  const [formData, setFormData] = useState<CreateProductRequest>({
    code: '',
    name: '',
    unit: '',
    unit_price: 0,
    reorder_point: 0,
  });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (field: keyof CreateProductRequest, value: string | number | undefined) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (!formData.code.trim()) {
      setError('商品コードを入力してください');
      return;
    }
    if (!formData.name.trim()) {
      setError('商品名を入力してください');
      return;
    }
    if (!formData.unit.trim()) {
      setError('単位を入力してください');
      return;
    }
    if (formData.unit_price < 0) {
      setError('単価は0以上を入力してください');
      return;
    }
    if (formData.reorder_point < 0) {
      setError('発注点は0以上を入力してください');
      return;
    }

    setSubmitting(true);

    try {
      await createProduct(formData);
      onSuccess();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'エラーが発生しました';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">商品追加</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* Code */}
          <div>
            <label htmlFor="code" className="block text-sm font-medium text-gray-700 mb-1">
              商品コード <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              id="code"
              value={formData.code}
              onChange={(e) => handleChange('code', e.target.value)}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="例: P001"
            />
          </div>

          {/* Name */}
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
              商品名 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              id="name"
              value={formData.name}
              onChange={(e) => handleChange('name', e.target.value)}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="例: 配管 25mm"
            />
          </div>

          {/* Spec */}
          <div>
            <label htmlFor="spec" className="block text-sm font-medium text-gray-700 mb-1">
              仕様 (任意)
            </label>
            <input
              type="text"
              id="spec"
              value={formData.spec || ''}
              onChange={(e) => handleChange('spec', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="例: ステンレス製"
            />
          </div>

          {/* Unit */}
          <div>
            <label htmlFor="unit" className="block text-sm font-medium text-gray-700 mb-1">
              単位 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              id="unit"
              value={formData.unit}
              onChange={(e) => handleChange('unit', e.target.value)}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="例: 本"
            />
          </div>

          {/* Unit Price */}
          <div>
            <label htmlFor="unit_price" className="block text-sm font-medium text-gray-700 mb-1">
              単価 (円) <span className="text-red-500">*</span>
            </label>
            <input
              type="number"
              id="unit_price"
              value={formData.unit_price}
              onChange={(e) => handleChange('unit_price', parseFloat(e.target.value) || 0)}
              min="0"
              step="0.01"
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="例: 1500"
            />
          </div>

          {/* Unit Weight */}
          <div>
            <label htmlFor="unit_weight" className="block text-sm font-medium text-gray-700 mb-1">
              単位重量 (kg) (任意)
            </label>
            <input
              type="number"
              id="unit_weight"
              value={formData.unit_weight || ''}
              onChange={(e) => handleChange('unit_weight', parseFloat(e.target.value) || undefined)}
              min="0"
              step="0.01"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="例: 2.5"
            />
          </div>

          {/* Reorder Point */}
          <div>
            <label htmlFor="reorder_point" className="block text-sm font-medium text-gray-700 mb-1">
              発注点 <span className="text-red-500">*</span>
            </label>
            <input
              type="number"
              id="reorder_point"
              value={formData.reorder_point}
              onChange={(e) => handleChange('reorder_point', parseInt(e.target.value, 10) || 0)}
              min="0"
              step="1"
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="例: 10"
            />
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
              {submitting ? '作成中...' : '作成'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
