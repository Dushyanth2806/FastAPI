from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import ExecutionTimeout, PyMongoError, ServerSelectionTimeoutError

import config
import queries
from db import get_db

app = FastAPI(title="Products & Suppliers (read-only extraction)")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS,
                   allow_methods=["GET"], allow_headers=["*"])


def run(fn, *args, **kwargs):
    """Run a query and map database errors without leaking details."""
    try:
        return fn(get_db(), *args, **kwargs)
    except (ServerSelectionTimeoutError, ExecutionTimeout):
        raise HTTPException(504, "Database timed out")
    except (PyMongoError, RuntimeError):
        raise HTTPException(503, "Database unavailable")


@app.get("/api/products")
def products(
    q: Optional[str] = Query(None, description="Search name or SKU"),
    department: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    supplier_id: Optional[int] = Query(None),
    low_stock_only: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return run(queries.search_products, q=q, department=department, category=category,
               supplier_id=supplier_id, low_stock_only=low_stock_only, skip=skip, limit=limit)


@app.get("/api/suppliers")
def suppliers():
    return run(queries.list_suppliers)


@app.get("/api/purchase-orders")
def purchase_orders(
    supplier_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    if not run(queries.purchase_orders_available):
        raise HTTPException(404, "Purchase orders collection not found; run check_schema.py")
    return run(queries.list_purchase_orders, supplier_id=supplier_id, status=status,
               skip=skip, limit=limit)
