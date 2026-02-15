from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import AppError
from app.models import Item, StockHead
from app.schemas import (
    DeleteItemEnvelope,
    ItemCreate,
    ItemDeleteResponse,
    ItemListEnvelope,
    ItemResponse,
    ItemUpdate,
    PaginationMeta,
    SingleItemEnvelope,
)

router = APIRouter(prefix="/api/v1/products", tags=["products"])


@router.post("", response_model=SingleItemEnvelope, status_code=201)
def create_item(body: ItemCreate, db: Session = Depends(get_db)):
    item = Item(**body.model_dump())
    db.add(item)
    try:
        db.flush()  # generate item.id before creating StockHead
        db.add(StockHead(item_id=item.id))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(
            "VALIDATION_ERROR",
            f"商品コード '{body.code}' は既に使用されています",
            400,
        )
    db.refresh(item)
    return SingleItemEnvelope(data=ItemResponse.model_validate(item))


@router.get("", response_model=ItemListEnvelope)
def list_items(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    active: Optional[bool] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Item)

    if active is not None:
        query = query.filter(Item.active == active)

    if q:
        pattern = f"%{q}%"
        query = query.filter(or_(Item.code.ilike(pattern), Item.name.ilike(pattern)))

    total = query.count()
    items = (
        query.order_by(Item.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return ItemListEnvelope(
        data=[ItemResponse.model_validate(i) for i in items],
        pagination=PaginationMeta(page=page, per_page=per_page, total=total),
    )


@router.get("/{item_id}", response_model=SingleItemEnvelope)
def get_item(item_id: UUID, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise AppError("PRODUCT_NOT_FOUND", f"商品が見つかりません: {item_id}", 404)
    return SingleItemEnvelope(data=ItemResponse.model_validate(item))


@router.patch("/{item_id}", response_model=SingleItemEnvelope)
def update_item(item_id: UUID, body: ItemUpdate, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise AppError("PRODUCT_NOT_FOUND", f"商品が見つかりません: {item_id}", 404)

    if item.version != body.version:
        raise AppError(
            "CONFLICT",
            f"バージョン競合: 現在={item.version}, 送信={body.version}",
            409,
        )

    update_data = body.model_dump(exclude_unset=True)
    update_data.pop("version")

    for key, value in update_data.items():
        setattr(item, key, value)

    item.version += 1

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(
            "VALIDATION_ERROR",
            f"商品コード '{body.code}' は既に使用されています",
            400,
        )

    db.refresh(item)
    return SingleItemEnvelope(data=ItemResponse.model_validate(item))


@router.delete("/{item_id}", response_model=DeleteItemEnvelope)
def delete_item(item_id: UUID, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise AppError("PRODUCT_NOT_FOUND", f"商品が見つかりません: {item_id}", 404)

    item.active = False
    item.version += 1
    db.commit()

    return DeleteItemEnvelope(data=ItemDeleteResponse(id=item.id, active=False))
