import { useState } from 'react';
import type { FormEvent } from 'react';
import { X } from 'lucide-react';
import { createProduct } from '../api/client';
import type { CreateProductRequest } from '../types/api';

interface CreateProductModalProps {
  onSuccess: () => void;
  onClose: () => void;
}

// Generate product code from name
function generateCode(name: string): string {
  const prefix = name
    .slice(0, 3)
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, '');
  const timestamp = Date.now().toString().slice(-6);
  return prefix + timestamp;
}

// Format number with thousand separators
function formatNumber(value: number): string {
  return value.toLocaleString('ja-JP');
}

// Parse formatted number string to number
function parseFormattedNumber(value: string): number | null {
  const cleaned = value.replace(/,/g, '').trim();
  if (!cleaned) return null;
  const num = parseFloat(cleaned);
  return isNaN(num) ? null : num;
}

export default function CreateProductModal({ onSuccess, onClose }: CreateProductModalProps) {
  const [name, setName] = useState('');
  const [spec, setSpec] = useState('');
  const [unitPriceText, setUnitPriceText] = useState('');
  const [unitWeightText, setUnitWeightText] = useState('');
  const [reorderPoint, setReorderPoint] = useState('');

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const validateField = (field: string, value: string): string | null => {
    switch (field) {
      case 'name':
        return !value.trim() ? '商品名を入力してください' : null;
      case 'unitPrice': {
        const num = parseFormattedNumber(value);
        if (num === null || num < 0) return '単価は0以上を入力してください';
        if (!Number.isInteger(num)) return '単価は整数で入力してください';
        return null;
      }
      case 'unitWeight': {
        if (!value.trim()) return null; // optional
        const num = parseFormattedNumber(value);
        if (num === null || num < 0) return '重量は0以上を入力してください';
        return null;
      }
      case 'reorderPoint': {
        const num = parseInt(value, 10);
        if (isNaN(num) || num < 0) return '発注点は0以上の整数を入力してください';
        return null;
      }
      default:
        return null;
    }
  };

  const handleBlur = (field: string) => {
    const error = validateField(field, getFieldValue(field));
    setErrors((prev) => {
      if (error) {
        return { ...prev, [field]: error };
      } else {
        const { [field]: _, ...rest } = prev;
        return rest;
      }
    });

    // Format number fields on blur
    if (field === 'unitPrice' && unitPriceText.trim()) {
      const num = parseFormattedNumber(unitPriceText);
      if (num !== null && num >= 0) {
        setUnitPriceText(formatNumber(num));
      }
    } else if (field === 'unitWeight' && unitWeightText.trim()) {
      const num = parseFormattedNumber(unitWeightText);
      if (num !== null && num >= 0) {
        setUnitWeightText(num.toString());
      }
    }
  };

  const getFieldValue = (field: string): string => {
    switch (field) {
      case 'name':
        return name;
      case 'unitPrice':
        return unitPriceText;
      case 'unitWeight':
        return unitWeightText;
      case 'reorderPoint':
        return reorderPoint;
      default:
        return '';
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    // Validate all fields
    const newErrors: Record<string, string> = {};
    const nameError = validateField('name', name);
    if (nameError) newErrors.name = nameError;

    const unitPriceError = validateField('unitPrice', unitPriceText);
    if (unitPriceError) newErrors.unitPrice = unitPriceError;

    const unitWeightError = validateField('unitWeight', unitWeightText);
    if (unitWeightError) newErrors.unitWeight = unitWeightError;

    const reorderPointError = validateField('reorderPoint', reorderPoint);
    if (reorderPointError) newErrors.reorderPoint = reorderPointError;

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    // Parse values
    const unitPrice = parseFormattedNumber(unitPriceText);
    const unitWeight = unitWeightText.trim()
      ? parseFormattedNumber(unitWeightText)
      : undefined;
    const reorderPointNum = parseInt(reorderPoint, 10);

    if (unitPrice === null || reorderPointNum === null || isNaN(reorderPointNum)) {
      setErrors({ submit: '入力値が不正です' });
      return;
    }

    setSubmitting(true);
    setErrors({});

    try {
      const requestData: CreateProductRequest = {
        code: generateCode(name),
        name: name.trim(),
        unit: '本', // Fixed value
        unit_price: unitPrice,
        reorder_point: reorderPointNum,
        spec: spec.trim() || undefined,
        unit_weight: unitWeight ?? undefined,
      };

      await createProduct(requestData);
      onSuccess();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'エラーが発生しました';
      setErrors({ submit: message });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg">
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
          {/* Name */}
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
              商品名 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onBlur={() => handleBlur('name')}
              className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 transition-all ${
                errors.name
                  ? 'border-red-300 focus:ring-red-500'
                  : 'border-gray-300 focus:ring-blue-500 focus:border-blue-500'
              }`}
              placeholder="例: 配管 25mm"
            />
            {errors.name && (
              <p className="mt-1 text-xs text-red-600">{errors.name}</p>
            )}
          </div>

          {/* Spec */}
          <div>
            <label htmlFor="spec" className="block text-sm font-medium text-gray-700 mb-1">
              仕様 (任意)
            </label>
            <input
              type="text"
              id="spec"
              value={spec}
              onChange={(e) => setSpec(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
              placeholder="例: ステンレス製"
            />
          </div>

          {/* Unit Price */}
          <div>
            <label htmlFor="unit_price" className="block text-sm font-medium text-gray-700 mb-1">
              単価 <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <input
                type="text"
                id="unit_price"
                value={unitPriceText}
                onChange={(e) => setUnitPriceText(e.target.value)}
                onBlur={() => handleBlur('unitPrice')}
                className={`w-full px-3 py-2 pr-10 border rounded-lg focus:outline-none focus:ring-2 transition-all ${
                  errors.unitPrice
                    ? 'border-red-300 focus:ring-red-500'
                    : 'border-gray-300 focus:ring-blue-500 focus:border-blue-500'
                }`}
                placeholder="例: 1500"
                inputMode="numeric"
              />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-gray-500 pointer-events-none">
                円
              </span>
            </div>
            {errors.unitPrice && (
              <p className="mt-1 text-xs text-red-600">{errors.unitPrice}</p>
            )}
          </div>

          {/* Unit Weight */}
          <div>
            <label htmlFor="unit_weight" className="block text-sm font-medium text-gray-700 mb-1">
              単位重量 (任意)
            </label>
            <div className="relative">
              <input
                type="text"
                id="unit_weight"
                value={unitWeightText}
                onChange={(e) => setUnitWeightText(e.target.value)}
                onBlur={() => handleBlur('unitWeight')}
                className={`w-full px-3 py-2 pr-12 border rounded-lg focus:outline-none focus:ring-2 transition-all ${
                  errors.unitWeight
                    ? 'border-red-300 focus:ring-red-500'
                    : 'border-gray-300 focus:ring-blue-500 focus:border-blue-500'
                }`}
                placeholder="例: 2.5"
                inputMode="decimal"
              />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-gray-500 pointer-events-none">
                kg
              </span>
            </div>
            {errors.unitWeight && (
              <p className="mt-1 text-xs text-red-600">{errors.unitWeight}</p>
            )}
          </div>

          {/* Reorder Point */}
          <div>
            <label htmlFor="reorder_point" className="block text-sm font-medium text-gray-700 mb-1">
              発注点 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              id="reorder_point"
              value={reorderPoint}
              onChange={(e) => setReorderPoint(e.target.value)}
              onBlur={() => handleBlur('reorderPoint')}
              className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 transition-all ${
                errors.reorderPoint
                  ? 'border-red-300 focus:ring-red-500'
                  : 'border-gray-300 focus:ring-blue-500 focus:border-blue-500'
              }`}
              placeholder="例: 10"
              inputMode="numeric"
            />
            {errors.reorderPoint && (
              <p className="mt-1 text-xs text-red-600">{errors.reorderPoint}</p>
            )}
          </div>

          {/* Submit Error */}
          {errors.submit && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded text-sm">
              {errors.submit}
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
