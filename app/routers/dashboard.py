from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    CategoryBreakdownItem,
    DashboardStockItem,
    DashboardTopEnvelope,
    OthersTotalSummary,
    StockByCategoryEnvelope,
)
from app.stock import query_stock_by_category, query_stock_top

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


# -- Stock Top ──────────────────────────────────────────────────────


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


# -- Stock by Category ─────────────────────────────────────────────


@router.get("/stock/by-category", response_model=StockByCategoryEnvelope)
def stock_by_category(
    metric: Literal["value", "qty", "available", "reserved"] = Query("value"),
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db),
):
    result = query_stock_by_category(db, metric=metric, limit=limit)
    return StockByCategoryEnvelope(
        metric=metric,
        total=result["total"],
        breakdown=[CategoryBreakdownItem(**b) for b in result["breakdown"]],
    )
