from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.sales import query_sales_pie
from app.schemas import (
    DashboardStockItem,
    DashboardTopEnvelope,
    OthersTotalSummary,
    PieBreakdownItem,
    PieRange,
    SalesPieEnvelope,
)
from app.stock import query_stock_top

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


# ── Stock Top ──────────────────────────────────────────────────────


@router.get("/stock/top", response_model=DashboardTopEnvelope)
def stock_top(
    metric: Literal["qty", "value"] = Query("qty"),
    limit: int = Query(10, ge=1, le=20),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
):
    top_items, others = query_stock_top(
        db, metric=metric, limit=limit, include_inactive=include_inactive,
    )
    return DashboardTopEnvelope(
        data=[DashboardStockItem(**item) for item in top_items],
        others_total=OthersTotalSummary(**others),
    )


# ── Sales Pie ──────────────────────────────────────────────────────


def _resolve_preset(preset: str) -> tuple[date, date]:
    """Convert preset name to (start, end) date range."""
    today = date.today()
    if preset == "month":
        return today.replace(day=1), today
    if preset == "3months":
        m = today.month - 2
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        return date(y, m, 1), today
    # year
    return date(today.year, 1, 1), today


@router.get("/sales/pie", response_model=SalesPieEnvelope)
def sales_pie(
    preset: Optional[Literal["month", "3months", "year"]] = Query(None),
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    group_by: Literal["product", "category"] = Query("product"),
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db),
):
    # Resolve period: custom start/end takes precedence over preset
    if start is not None and end is not None:
        range_start, range_end = start, end
        range_preset = None
    else:
        effective_preset = preset or "month"
        range_start, range_end = _resolve_preset(effective_preset)
        range_preset = effective_preset

    result = query_sales_pie(db, start=range_start, end=range_end, limit=limit)

    return SalesPieEnvelope(
        range=PieRange(start=range_start, end=range_end, preset=range_preset),
        total_yen=result["total_yen"],
        refund_total_yen=result["refund_total_yen"],
        breakdown=[PieBreakdownItem(**b) for b in result["breakdown"]],
    )
