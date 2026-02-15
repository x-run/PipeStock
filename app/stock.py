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
# Resolve TxCreate → (bucket, qty_delta) — single source of truth
# ------------------------------------------------------------------

_TX_RESOLVE: dict[str, tuple[str, int]] = {
    # type → (bucket, sign multiplier)
    "IN":        ("ON_HAND",   +1),
    "OUT":       ("ON_HAND",   -1),
    "RESERVE":   ("RESERVED",  +1),
    "UNRESERVE": ("RESERVED",  -1),
}


def resolve_tx(tx: TxCreate) -> tuple[str, str, int]:
    """Derive (db_type, bucket, qty_delta) from a safe TxCreate input."""
    if tx.type == "ADJUST":
        sign = +1 if tx.direction == "INCREASE" else -1
        return "ADJUST", "ON_HAND", sign * tx.qty
    bucket, sign = _TX_RESOLVE[tx.type]
    return tx.type, bucket, sign * tx.qty


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

    # Resolve all inputs to (type, bucket, qty_delta)
    resolved = [resolve_tx(tx) for tx in tx_inputs]

    # --- project new stock after ALL txs ---
    current = calc_stock(db, item.id)

    delta_on_hand = sum(qd for _, b, qd in resolved if b == "ON_HAND")
    delta_reserved = sum(qd for _, b, qd in resolved if b == "RESERVED")

    new_on_hand = current.on_hand + delta_on_hand
    new_reserved = current.reserved + delta_reserved
    new_available = new_on_hand - new_reserved

    # INV-1
    if new_on_hand < 0:
        raise AppError(
            "INSUFFICIENT_ON_HAND",
            f"On-hand 不足: 現在={current.on_hand}, 操作後={new_on_hand}",
            409,
        )

    # INV-2
    if new_reserved < 0:
        raise AppError(
            "INSUFFICIENT_RESERVED",
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

    # --- persist atomically (SAVEPOINT) ---
    created: list[InventoryTx] = []
    try:
        with db.begin_nested():
            for tx_input, (db_type, bucket, qty_delta) in zip(tx_inputs, resolved):
                entity = InventoryTx(
                    item_id=item.id,
                    type=db_type,
                    bucket=bucket,
                    qty_delta=qty_delta,
                    reason=tx_input.reason,
                    request_id=tx_input.request_id,
                )
                db.add(entity)
                created.append(entity)
            db.flush()
    except IntegrityError:
        raise AppError(
            "DUPLICATE_REQUEST_ID",
            "request_id が重複しています",
            409,
        )

    db.commit()

    for entity in created:
        db.refresh(entity)

    new_stock = StockLevel(
        on_hand=new_on_hand,
        reserved=new_reserved,
        available=new_available,
    )
    return created, new_stock
