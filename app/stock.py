"""Stock calculation and transaction creation service.

All inventory quantities are derived from SUM(inventory_tx.qty_delta).
No mutable stock table exists — this module is the single source of truth.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import InventoryTx, Item

if TYPE_CHECKING:
    from app.schemas import TxCreate


# ------------------------------------------------------------------
# Stock calculation
# ------------------------------------------------------------------

@dataclass(frozen=True)
class StockLevel:
    on_hand: int
    reserved: int
    available: int


def calc_stock(db: Session, item_id: uuid.UUID) -> StockLevel:
    """Aggregate on_hand / reserved from inventory_tx rows."""
    rows = (
        db.query(
            InventoryTx.bucket,
            func.coalesce(func.sum(InventoryTx.qty_delta), 0),
        )
        .filter(InventoryTx.item_id == item_id)
        .group_by(InventoryTx.bucket)
        .all()
    )
    on_hand = 0
    reserved = 0
    for bucket, total in rows:
        if bucket == "ON_HAND":
            on_hand = int(total)
        elif bucket == "RESERVED":
            reserved = int(total)
    return StockLevel(on_hand=on_hand, reserved=reserved, available=on_hand - reserved)


# ------------------------------------------------------------------
# Transaction creation (single + batch share the same path)
# ------------------------------------------------------------------

def create_txs(
    db: Session,
    item: Item,
    tx_inputs: list[TxCreate],
) -> tuple[list[InventoryTx], StockLevel]:
    """Validate invariants and persist transactions atomically.

    Returns the created ORM objects and the projected stock level.
    Raises AppError on any invariant violation.
    """

    # INV-8: inactive item
    if not item.active:
        raise AppError(
            "PRODUCT_INACTIVE",
            f"非アクティブ商品には操作できません: {item.code}",
            400,
        )

    # INV-6: ADJUST only for ON_HAND
    for tx in tx_inputs:
        if tx.type == "ADJUST" and tx.bucket != "ON_HAND":
            raise AppError(
                "VALIDATION_ERROR",
                "ADJUST は ON_HAND バケットのみに適用可能です",
                400,
            )

    # --- project new stock after ALL txs ---
    current = calc_stock(db, item.id)

    delta_on_hand = sum(tx.qty_delta for tx in tx_inputs if tx.bucket == "ON_HAND")
    delta_reserved = sum(tx.qty_delta for tx in tx_inputs if tx.bucket == "RESERVED")

    new_on_hand = current.on_hand + delta_on_hand
    new_reserved = current.reserved + delta_reserved
    new_available = new_on_hand - new_reserved

    # INV-1
    if new_on_hand < 0:
        raise AppError(
            "INSUFFICIENT_AVAILABLE",
            f"On-hand 不足: 現在={current.on_hand}, 操作後={new_on_hand}",
            409,
        )

    # INV-2
    if new_reserved < 0:
        raise AppError(
            "INSUFFICIENT_AVAILABLE",
            f"Reserved 不足: 現在={current.reserved}, 操作後={new_reserved}",
            409,
        )

    # INV-3
    if new_available < 0:
        raise AppError(
            "INSUFFICIENT_AVAILABLE",
            f"Available 不足: 現在={current.available}, 操作後={new_available}",
            409,
        )

    # --- persist ---
    created: list[InventoryTx] = []
    for tx in tx_inputs:
        entity = InventoryTx(
            item_id=item.id,
            type=tx.type,
            bucket=tx.bucket,
            qty_delta=tx.qty_delta,
            reason=tx.reason,
            request_id=tx.request_id,
        )
        db.add(entity)
        created.append(entity)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(
            "VALIDATION_ERROR",
            "request_id が重複しています",
            400,
        )

    for entity in created:
        db.refresh(entity)

    new_stock = StockLevel(
        on_hand=new_on_hand,
        reserved=new_reserved,
        available=new_available,
    )
    return created, new_stock
