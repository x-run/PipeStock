import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { fetchStockTop, fetchStockByCategory } from '../api/client';
import type { DashboardTopResponse, StockByCategoryResponse } from '../types/api';
import StockBarChart from '../components/StockBarChart';
import CategoryPieChart from '../components/CategoryPieChart';
import KpiCards from '../components/KpiCards';
import Spinner from '../components/Spinner';
import ErrorMessage from '../components/ErrorMessage';

type MetricKey = 'value' | 'qty' | 'available' | 'reserved';
const METRIC_LABELS: Record<MetricKey, string> = {
  value: '金額',
  qty: '数量',
  available: '利用可能',
  reserved: '引当',
};

export default function DashboardPage() {
  const [topData, setTopData] = useState<DashboardTopResponse | null>(null);
  const [catData, setCatData] = useState<StockByCategoryResponse | null>(null);
  const [metric, setMetric] = useState<MetricKey>('value');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    Promise.all([fetchStockTop(10), fetchStockByCategory(metric, 10)])
      .then(([top, cat]) => {
        setTopData(top);
        setCatData(cat);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, [metric]);

  if (loading) return <Spinner />;
  if (error) return <ErrorMessage message={error} onRetry={load} />;
  if (!topData || !catData) return null;

  const totalItemCount = topData.data.length + (topData.others_total.on_hand > 0 ? 1 : 0);

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <KpiCards items={topData.data} totalItemCount={totalItemCount} />

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Bar chart — 2/3 width */}
        <div className="lg:col-span-2 rounded-xl border border-gray-200 bg-white p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-gray-900">
              在庫数量 Top 10
            </h2>
            <Link
              to="/stock"
              className="flex items-center gap-1 text-sm font-medium text-blue-600 hover:text-blue-800 cursor-pointer transition-colors"
            >
              もっと見る
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          {topData.data.length === 0 ? (
            <p className="text-sm text-gray-400 py-8 text-center">商品がありません</p>
          ) : (
            <StockBarChart items={topData.data} others={topData.others_total} />
          )}
        </div>

        {/* Pie chart — 1/3 width */}
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-gray-900">
              在庫構成比
            </h2>
            <select
              value={metric}
              onChange={(e) => setMetric(e.target.value as MetricKey)}
              className="text-sm border border-gray-300 rounded-md px-2 py-1 cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {Object.entries(METRIC_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>

          {catData.breakdown.length === 0 ? (
            <p className="text-sm text-gray-400 py-8 text-center">データなし</p>
          ) : (
            <CategoryPieChart
              breakdown={catData.breakdown}
              total={catData.total}
              metric={metric}
            />
          )}
        </div>
      </div>
    </div>
  );
}
