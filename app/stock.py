"""Stock calculation and transaction creation service.

All inventory quantities are derived from SUM(inventory_tx.qty_delta).
No mutable stock table exists — this module is the single source of truth.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import and_, case, func, or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import re

from app.errors import AppError
from app.models import InventoryTx, Item, StockHead

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

    # Read current optimistic-lock version
    stock_head = db.query(StockHead).filter(StockHead.item_id == item.id).first()
    if stock_head is None:
        raise AppError(
            "CONFLICT",
            f"stock_heads レコードが見つかりません: {item.id}",
            409,
        )
    expected_version = stock_head.version

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
            # Optimistic lock: bump version WHERE version == expected
            rows_updated = db.execute(
                update(StockHead)
                .where(StockHead.item_id == item.id)
                .where(StockHead.version == expected_version)
                .values(version=expected_version + 1)
            ).rowcount

            if rows_updated == 0:
                raise AppError(
                    "CONFLICT",
                    "在庫の楽観ロック競合が発生しました。再試行してください。",
                    409,
                )

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
    except AppError:
        raise
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


# ------------------------------------------------------------------
# Bulk stock breakdown (dashboard / stock list)
# ------------------------------------------------------------------

def _stock_breakdown_subquery(db: Session):
    """Per-item stock aggregation with reason-level breakdown."""
    return (
        db.query(
            InventoryTx.item_id.label("item_id"),
            func.coalesce(func.sum(case(
                (InventoryTx.bucket == "ON_HAND", InventoryTx.qty_delta),
                else_=0,
            )), 0).label("on_hand"),
            func.coalesce(func.sum(case(
                (InventoryTx.bucket == "RESERVED", InventoryTx.qty_delta),
                else_=0,
            )), 0).label("reserved_total"),
            func.coalesce(func.sum(case(
                (and_(InventoryTx.bucket == "RESERVED",
                      InventoryTx.reason == "RETURN_PENDING"),
                 InventoryTx.qty_delta),
                else_=0,
            )), 0).label("reserved_pending_return"),
            func.coalesce(func.sum(case(
                (and_(InventoryTx.bucket == "RESERVED",
                      InventoryTx.reason == "ORDER_PENDING_SHIPMENT"),
                 InventoryTx.qty_delta),
                else_=0,
            )), 0).label("reserved_pending_order"),
        )
        .group_by(InventoryTx.item_id)
        .subquery()
    )


def _row_to_stock_item(row, *, include_detail: bool = False) -> dict:
    """Convert a query row to a stock item dict."""
    oh = int(row.on_hand)
    rt = int(row.reserved_total)
    avail = oh - rt
    d: dict = {
        "product_id": row.product_id,
        "code": row.code,
        "name": row.name,
        "unit": row.unit,
        "on_hand": oh,
        "reserved_total": rt,
        "reserved_pending_return": int(row.reserved_pending_return),
        "reserved_pending_order": int(row.reserved_pending_order),
        "available": avail,
        "reorder_point": row.reorder_point,
        "needs_reorder": avail <= row.reorder_point,
    }
    if include_detail:
        d["spec"] = row.spec
        d["unit_price"] = row.unit_price
        d["unit_weight"] = row.unit_weight
        d["stock_value"] = oh * row.unit_price
    return d


def query_stock_top(
    db: Session,
    *,
    limit: int = 10,
    include_inactive: bool = False,
) -> tuple[list[dict], dict]:
    """Return (top_items, others_total) for dashboard bar chart (qty-only)."""
    sq = _stock_breakdown_subquery(db)

    on_hand_expr = func.coalesce(sq.c.on_hand, 0)

    query = (
        db.query(
            Item.id.label("product_id"),
            Item.code,
            Item.name,
            Item.unit,
            Item.reorder_point,
            on_hand_expr.label("on_hand"),
            func.coalesce(sq.c.reserved_total, 0).label("reserved_total"),
            func.coalesce(sq.c.reserved_pending_return, 0).label("reserved_pending_return"),
            func.coalesce(sq.c.reserved_pending_order, 0).label("reserved_pending_order"),
        )
        .outerjoin(sq, Item.id == sq.c.item_id)
    )

    if not include_inactive:
        query = query.filter(Item.active == True)  # noqa: E712

    rows = query.order_by(on_hand_expr.desc(), Item.code).all()

    top = [_row_to_stock_item(r) for r in rows[:limit]]

    others: dict = {
        "on_hand": 0, "reserved_total": 0,
        "reserved_pending_return": 0, "reserved_pending_order": 0,
        "available": 0,
    }
    for r in rows[limit:]:
        oh = int(r.on_hand)
        rt = int(r.reserved_total)
        others["on_hand"] += oh
        others["reserved_total"] += rt
        others["reserved_pending_return"] += int(r.reserved_pending_return)
        others["reserved_pending_order"] += int(r.reserved_pending_order)
        others["available"] += oh - rt

    return top, others


def query_stock_list(
    db: Session,
    *,
    q: str | None = None,
    sort: str = "qty_desc",
    page: int = 1,
    per_page: int = 20,
    include_inactive: bool = False,
) -> tuple[list[dict], int]:
    """Return (items, total_count) for stock list with search/sort/pagination."""
    sq = _stock_breakdown_subquery(db)

    on_hand_expr = func.coalesce(sq.c.on_hand, 0)
    reserved_total_expr = func.coalesce(sq.c.reserved_total, 0)
    stock_value_expr = on_hand_expr * Item.unit_price

    # --- Count (items only, no join needed) ---
    count_q = db.query(func.count(Item.id))
    if not include_inactive:
        count_q = count_q.filter(Item.active == True)  # noqa: E712
    if q:
        pattern = f"%{q}%"
        count_q = count_q.filter(or_(
            Item.code.ilike(pattern),
            Item.name.ilike(pattern),
            Item.spec.ilike(pattern),
        ))
    total = count_q.scalar()

    # --- Data ---
    data_q = (
        db.query(
            Item.id.label("product_id"),
            Item.code,
            Item.name,
            Item.spec,
            Item.unit,
            Item.unit_price,
            Item.unit_weight,
            Item.reorder_point,
            on_hand_expr.label("on_hand"),
            reserved_total_expr.label("reserved_total"),
            func.coalesce(sq.c.reserved_pending_return, 0).label("reserved_pending_return"),
            func.coalesce(sq.c.reserved_pending_order, 0).label("reserved_pending_order"),
        )
        .outerjoin(sq, Item.id == sq.c.item_id)
    )

    if not include_inactive:
        data_q = data_q.filter(Item.active == True)  # noqa: E712
    if q:
        pattern = f"%{q}%"
        data_q = data_q.filter(or_(
            Item.code.ilike(pattern),
            Item.name.ilike(pattern),
            Item.spec.ilike(pattern),
        ))

    sort_map = {
        "qty_desc": on_hand_expr.desc(),
        "qty_asc": on_hand_expr.asc(),
        "value_desc": stock_value_expr.desc(),
        "value_asc": stock_value_expr.asc(),
        "updated_desc": Item.updated_at.desc(),
    }
    data_q = data_q.order_by(sort_map.get(sort, on_hand_expr.desc()), Item.code)

    rows = data_q.offset((page - 1) * per_page).limit(per_page).all()

    return [_row_to_stock_item(r, include_detail=True) for r in rows], total


# ------------------------------------------------------------------
# Category-based stock aggregation
# ------------------------------------------------------------------

_SPLIT_RE = re.compile(r"[\s\u3000]+")


def _extract_category(name: str) -> str:
    """Extract category from product name (first token, full-width space aware)."""
    token = _SPLIT_RE.split(name, maxsplit=1)[0]
    return token or name


def query_stock_by_category(
    db: Session,
    *,
    metric: str = "value",
    limit: int = 10,
) -> dict:
    """Aggregate stock by category (first word of name) for pie chart.

    Returns { total, breakdown: [{key, label, metric_value}] }.
    """
    sq = _stock_breakdown_subquery(db)

    on_hand_expr = func.coalesce(sq.c.on_hand, 0)
    reserved_expr = func.coalesce(sq.c.reserved_total, 0)

    rows = (
        db.query(
            Item.name,
            on_hand_expr.label("on_hand"),
            reserved_expr.label("reserved_total"),
            Item.unit_price,
        )
        .outerjoin(sq, Item.id == sq.c.item_id)
        .filter(Item.active == True)  # noqa: E712
        .all()
    )

    # Group by category in Python (category is a derived value, not in DB)
    cat_map: dict[str, float] = {}
    for r in rows:
        cat = _extract_category(r.name)
        oh = int(r.on_hand)
        rt = int(r.reserved_total)
        if metric == "value":
            val = oh * r.unit_price
        elif metric == "qty":
            val = oh
        elif metric == "available":
            val = oh - rt
        else:  # reserved
            val = rt
        cat_map[cat] = cat_map.get(cat, 0) + val

    # Sort descending by metric_value
    sorted_cats = sorted(cat_map.items(), key=lambda x: x[1], reverse=True)

    total = sum(v for _, v in sorted_cats)

    breakdown: list[dict] = []
    for key, val in sorted_cats[:limit]:
        breakdown.append({"key": key, "label": key, "metric_value": val})

    if len(sorted_cats) > limit:
        other_sum = sum(v for _, v in sorted_cats[limit:])
        breakdown.append({"key": "OTHER", "label": "その他", "metric_value": other_sum})

    return {"total": total, "breakdown": breakdown}
