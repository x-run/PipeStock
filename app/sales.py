"""Sales query service — pie chart aggregation."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from app.models import Item, SalesEvent


def query_sales_pie(
    db: Session,
    *,
    start: date,
    end: date,
    limit: int = 10,
) -> dict:
    """Aggregate sales by product for pie chart (TopN + OTHER)."""
    start_dt = datetime.combine(start, time.min)
    end_dt = datetime.combine(end + timedelta(days=1), time.min)

    cond = and_(
        SalesEvent.occurred_at >= start_dt,
        SalesEvent.occurred_at < end_dt,
    )

    # --- Totals ---
    row = db.query(
        func.coalesce(func.sum(SalesEvent.amount_yen), 0),
        func.coalesce(func.sum(case(
            (SalesEvent.type == "REFUND", SalesEvent.amount_yen),
            else_=0,
        )), 0),
    ).filter(cond).first()

    total_yen = int(row[0])
    refund_total_yen = int(row[1])

    # --- Group by product ---
    groups = (
        db.query(
            SalesEvent.product_id,
            func.sum(SalesEvent.amount_yen).label("amount_yen"),
        )
        .filter(cond)
        .group_by(SalesEvent.product_id)
        .order_by(func.sum(SalesEvent.amount_yen).desc())
        .all()
    )

    # Fetch product labels
    product_ids = [g.product_id for g in groups if g.product_id is not None]
    labels: dict = {}
    if product_ids:
        for item in db.query(Item.id, Item.code, Item.name).filter(
            Item.id.in_(product_ids)
        ).all():
            labels[item.id] = f"{item.code} {item.name}"

    # Build breakdown: TopN + OTHER
    breakdown: list[dict] = []
    for g in groups[:limit]:
        if g.product_id is None:
            breakdown.append({
                "key": "UNKNOWN",
                "label": "不明な商品",
                "amount_yen": int(g.amount_yen),
            })
        else:
            breakdown.append({
                "key": str(g.product_id),
                "label": labels.get(g.product_id, str(g.product_id)),
                "amount_yen": int(g.amount_yen),
            })

    if len(groups) > limit:
        other_sum = sum(int(g.amount_yen) for g in groups[limit:])
        breakdown.append({
            "key": "OTHER",
            "label": "その他",
            "amount_yen": other_sum,
        })

    return {
        "total_yen": total_yen,
        "refund_total_yen": refund_total_yen,
        "breakdown": breakdown,
    }
