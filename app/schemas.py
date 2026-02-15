import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


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
