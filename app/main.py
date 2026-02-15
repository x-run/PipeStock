from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from sqlalchemy import text

from app.database import Base, engine
from app.errors import AppError
from app.routers import items, transactions

import app.models  # noqa: F401 – register all models with Base.metadata

Base.metadata.create_all(bind=engine)

# Backfill stock_heads for items created before the table existed
with engine.begin() as conn:
    conn.execute(text(
        "INSERT OR IGNORE INTO stock_heads (item_id, version, updated_at) "
        "SELECT id, 0, updated_at FROM items"
    ))

app = FastAPI(title="PipeStock", version="0.1.0")
app.include_router(items.router)
app.include_router(transactions.router)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"error": {"code": "VALIDATION_ERROR", "message": str(exc)}},
    )
