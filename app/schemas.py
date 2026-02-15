import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------- Request ----------

class ItemCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    spec: Optional[str] = Field(None, max_length=500)
    unit: str = Field(..., min_length=1, max_length=20)
    unit_price: float = Field(..., ge=0)
    unit_weight: Optional[float] = Field(None, ge=0)
    reorder_point: int = Field(..., ge=0)


class ItemUpdate(BaseModel):
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    spec: Optional[str] = Field(None, max_length=500)
    unit: Optional[str] = Field(None, min_length=1, max_length=20)
    unit_price: Optional[float] = Field(None, ge=0)
    unit_weight: Optional[float] = Field(None, ge=0)
    reorder_point: Optional[int] = Field(None, ge=0)
    version: int


# ---------- Response ----------

class ItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    spec: Optional[str]
    unit: str
    unit_price: float
    unit_weight: Optional[float]
    reorder_point: int
    active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class ItemDeleteResponse(BaseModel):
    id: uuid.UUID
    active: bool


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int


class ItemListEnvelope(BaseModel):
    data: list[ItemResponse]
    pagination: PaginationMeta


class SingleItemEnvelope(BaseModel):
    data: ItemResponse


class DeleteItemEnvelope(BaseModel):
    data: ItemDeleteResponse


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


# ---------- Transaction ----------

class TxCreate(BaseModel):
    type: Literal["IN", "OUT", "ADJUST", "RESERVE", "UNRESERVE"]
    qty: int = Field(..., ge=1)
    direction: Optional[Literal["INCREASE", "DECREASE"]] = None
    reason: Optional[str] = Field(None, max_length=500)
    request_id: Optional[uuid.UUID] = None

    @model_validator(mode="after")
    def check_direction(self) -> "TxCreate":
        if self.type == "ADJUST":
            if self.direction is None:
                raise ValueError("ADJUST requires direction (INCREASE or DECREASE)")
        else:
            if self.direction is not None:
                raise ValueError(f"{self.type} does not accept direction")
        return self


class TxBatchCreate(BaseModel):
    transactions: list[TxCreate] = Field(..., min_length=1, max_length=10)


class TxResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    product_id: uuid.UUID = Field(validation_alias="item_id")
    type: str
    bucket: str
    qty_delta: int
    reason: Optional[str]
    created_at: datetime = Field(validation_alias="occurred_at")


class StockSummary(BaseModel):
    available: int
    on_hand: int
    reserved: int


class TxCreateEnvelope(BaseModel):
    data: TxResponse
    stock: StockSummary


class TxBatchEnvelope(BaseModel):
    data: list[TxResponse]
    stock: StockSummary


class TxListEnvelope(BaseModel):
    data: list[TxResponse]
    pagination: PaginationMeta
