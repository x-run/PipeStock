import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Item(Base):
    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    spec: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_price: Mapped[float] = mapped_column(
        Numeric(10, 2, asdecimal=False), nullable=False
    )
    unit_weight: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 3, asdecimal=False), nullable=True
    )
    reorder_point: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )


class InventoryTx(Base):
    __tablename__ = "inventory_tx"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("items.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    bucket: Mapped[str] = mapped_column(String(10), nullable=False)
    qty_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    request_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, unique=True, nullable=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )

    item: Mapped["Item"] = relationship("Item")

    __table_args__ = (
        Index("ix_inventory_tx_item_occurred", "item_id", "occurred_at"),
        Index("ix_inventory_tx_bucket_occurred", "bucket", "occurred_at"),
    )
