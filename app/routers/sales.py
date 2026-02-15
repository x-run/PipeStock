from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import AppError
from app.models import Item, SalesEvent
from app.schemas import SalesCreate, SalesResponse, SingleSalesEnvelope

router = APIRouter(prefix="/api/v1", tags=["sales"])


@router.post("/sales", response_model=SingleSalesEnvelope, status_code=201)
def create_sale(body: SalesCreate, db: Session = Depends(get_db)):
    # Validate product_id if provided
    if body.product_id is not None:
        item = db.query(Item).filter(Item.id == body.product_id).first()
        if not item:
            raise AppError(
                "PRODUCT_NOT_FOUND",
                f"商品が見つかりません: {body.product_id}",
                404,
            )

    # Safe sign conversion: REFUND → negative
    amount = body.amount_yen if body.type == "SALE" else -body.amount_yen

    event = SalesEvent(
        type=body.type,
        amount_yen=amount,
        product_id=body.product_id,
        note=body.note,
        request_id=body.request_id,
        occurred_at=body.occurred_at or datetime.now(timezone.utc),
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError("DUPLICATE_REQUEST_ID", "request_id が重複しています", 409)

    db.refresh(event)
    return SingleSalesEnvelope(data=SalesResponse.model_validate(event))
