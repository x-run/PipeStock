from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import PaginationMeta, StockListEnvelope, StockListItem
from app.stock import query_stock_list

router = APIRouter(prefix="/api/v1", tags=["stock"])


@router.get("/stock", response_model=StockListEnvelope)
def list_stock(
    q: Optional[str] = None,
    sort: Literal[
        "qty_desc", "qty_asc", "value_desc", "value_asc", "updated_desc"
    ] = Query("qty_desc"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
):
    items, total = query_stock_list(
        db, q=q, sort=sort, page=page, per_page=per_page,
        include_inactive=include_inactive,
    )
    return StockListEnvelope(
        data=[StockListItem(**item) for item in items],
        pagination=PaginationMeta(page=page, per_page=per_page, total=total),
    )
