import type {
  DashboardTopResponse,
  StockByCategoryResponse,
  StockListResponse,
} from '../types/api';

const BASE = '/api/v1';

async function get<T>(url: string): Promise<T> {
  const res = await fetch(`${BASE}${url}`);
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export function fetchStockTop(limit = 10): Promise<DashboardTopResponse> {
  return get(`/dashboard/stock/top?limit=${limit}`);
}

export function fetchStockByCategory(
  metric = 'value',
  limit = 10,
): Promise<StockByCategoryResponse> {
  return get(`/dashboard/stock/by-category?metric=${metric}&limit=${limit}`);
}

export interface StockListParams {
  q?: string;
  sort?: string;
  page?: number;
  per_page?: number;
}

export function fetchStockList(params: StockListParams = {}): Promise<StockListResponse> {
  const sp = new URLSearchParams();
  if (params.q) sp.set('q', params.q);
  if (params.sort) sp.set('sort', params.sort);
  if (params.page) sp.set('page', String(params.page));
  if (params.per_page) sp.set('per_page', String(params.per_page));
  const qs = sp.toString();
  return get(`/stock${qs ? `?${qs}` : ''}`);
}
