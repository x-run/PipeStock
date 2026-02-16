// -- Dashboard Stock Top --

export interface DashboardStockItem {
  product_id: string;
  code: string;
  name: string;
  unit: string;
  on_hand: number;
  reserved_total: number;
  reserved_pending_return: number;
  reserved_pending_order: number;
  available: number;
  reorder_point: number;
  needs_reorder: boolean;
}

export interface OthersTotalSummary {
  on_hand: number;
  reserved_total: number;
  reserved_pending_return: number;
  reserved_pending_order: number;
  available: number;
}

export interface DashboardTopResponse {
  data: DashboardStockItem[];
  others_total: OthersTotalSummary;
}

// -- Category --

export interface CategoryBreakdownItem {
  key: string;
  label: string;
  metric_value: number;
}

export interface StockByCategoryResponse {
  metric: string;
  total: number;
  breakdown: CategoryBreakdownItem[];
}

// -- Stock List --

export interface StockListItem {
  product_id: string;
  code: string;
  name: string;
  spec: string | null;
  unit: string;
  unit_price: number;
  unit_weight: number | null;
  reorder_point: number;
  on_hand: number;
  reserved_total: number;
  reserved_pending_return: number;
  reserved_pending_order: number;
  available: number;
  stock_value: number;
  needs_reorder: boolean;
}

export interface PaginationMeta {
  page: number;
  per_page: number;
  total: number;
}

export interface StockListResponse {
  data: StockListItem[];
  pagination: PaginationMeta;
}
