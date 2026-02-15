from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import AppError
from app.models import InventoryTx, Item
from app.schemas import (
    PaginationMeta,
    StockSummary,
    TxBatchCreate,
    TxBatchEnvelope,
    TxCreate,
    TxCreateEnvelope,
    TxListEnvelope,
    TxResponse,
)
from app.stock import create_txs

router = APIRouter(prefix="/api/v1/products", tags=["transactions"])


def _get_item_or_404(db: Session, product_id: UUID) -> Item:
    item = db.query(Item).filter(Item.id == product_id).first()
    if not item:
        raise AppError("PRODUCT_NOT_FOUND", f"商品が見つかりません: {product_id}", 404)
    return item


def _stock_summary(stock) -> StockSummary:
    return StockSummary(
        available=stock.available,
        on_hand=stock.on_hand,
        reserved=stock.reserved,
    )


# ------------------------------------------------------------------
# POST /api/v1/products/{product_id}/transactions
# ------------------------------------------------------------------
@router.post(
    "/{product_id}/transactions",
    response_model=TxCreateEnvelope,
    status_code=201,
)
def create_transaction(
    product_id: UUID,
    body: TxCreate,
    db: Session = Depends(get_db),
):
    item = _get_item_or_404(db, product_id)
    created, stock = create_txs(db, item, [body])
    return TxCreateEnvelope(
        data=TxResponse.model_validate(created[0]),
        stock=_stock_summary(stock),
    )


# ------------------------------------------------------------------
# POST /api/v1/products/{product_id}/transactions/batch
# ------------------------------------------------------------------
@router.post(
    "/{product_id}/transactions/batch",
    response_model=TxBatchEnvelope,
    status_code=201,
)
def create_transactions_batch(
    product_id: UUID,
    body: TxBatchCreate,
    db: Session = Depends(get_db),
):
    item = _get_item_or_404(db, product_id)
    created, stock = create_txs(db, item, body.transactions)
    return TxBatchEnvelope(
        data=[TxResponse.model_validate(tx) for tx in created],
        stock=_stock_summary(stock),
    )


# ------------------------------------------------------------------
# GET /api/v1/products/{product_id}/transactions
# ------------------------------------------------------------------
@router.get(
    "/{product_id}/transactions",
    response_model=TxListEnvelope,
)
def list_transactions(
    product_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    type: Optional[str] = None,
    bucket: Optional[str] = None,
    db: Session = Depends(get_db),
):
    _get_item_or_404(db, product_id)

    query = db.query(InventoryTx).filter(InventoryTx.item_id == product_id)

    if type is not None:
        query = query.filter(InventoryTx.type == type)
    if bucket is not None:
        query = query.filter(InventoryTx.bucket == bucket)

    total = query.count()
    rows = (
        query.order_by(InventoryTx.occurred_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return TxListEnvelope(
        data=[TxResponse.model_validate(r) for r in rows],
        pagination=PaginationMeta(page=page, per_page=per_page, total=total),
    )
