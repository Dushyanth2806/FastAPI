"""
Products & Suppliers connector for Claude Desktop (read-only).

Tools over neerus.inventory (products) and neerus.suppliers. Settings come from
../backend/.env (same file the FastAPI backend uses). Nothing here can write data.
"""
import functools
import os
import re
from pathlib import Path

from bson import ObjectId
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

MONGODB_URI = os.getenv("MONGODB_URI", "")
DB_NAME = os.getenv("DATABASE_NAME", "neerus")
PRODUCTS = os.getenv("PRODUCTS_COLLECTION", "inventory")
SUPPLIERS = os.getenv("SUPPLIERS_COLLECTION", "suppliers")
LOW_STOCK = int(os.getenv("LOW_STOCK_THRESHOLD", "10"))
MAX_ROWS = 100

# Total units is not stored: it is the sum of the per-store stock dict.
TOTAL_UNITS = {"$sum": {"$map": {"input": {"$objectToArray": {"$ifNull": ["$stock", {}]}},
                                 "as": "s", "in": {"$ifNull": ["$$s.v", 0]}}}}

_client = None


def _db():
    global _client
    if _client is None:
        if not MONGODB_URI or MONGODB_URI.startswith("<") or MONGODB_URI.startswith("your-"):
            raise RuntimeError("MONGODB_URI is not set in products-suppliers-management/backend/.env")
        _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=8000, socketTimeoutMS=15000)
    return _client[DB_NAME]


def _clean(v):
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_clean(x) for x in v]
    return v


def _safe(fn):
    """Return errors as data so Claude can correct itself, without leaking the URI."""
    @functools.wraps(fn)  # keeps the real signature, which FastMCP reads to build the tool schema
    def wrapper(*a, **k):
        try:
            return fn(*a, **k)
        except Exception as e:
            return {"error": f"{e.__class__.__name__}: {str(e)[:200]}"}
    return wrapper


def _supplier_names() -> dict:
    return {s["_id"]: s.get("name") for s in _db()[SUPPLIERS].find({}, {"name": 1})}


def _product_view(p: dict, names: dict) -> dict:
    stock = p.get("stock") or {}
    total = sum(v for v in stock.values() if isinstance(v, (int, float)))
    p = dict(p)
    p["total_units"] = total
    p["low_stock"] = total <= LOW_STOCK
    p["supplier_names"] = [names.get(i, f"(missing supplier {i})") for i in p.get("suppliers") or []]
    p.pop("size", None)  # always null
    return p


mcp = FastMCP(
    "products-suppliers",
    instructions=(
        "Read-only tools for the product catalogue (neerus.inventory) and suppliers (neerus.suppliers). "
        f"Total units per product = sum of its per-store stock; low stock means total <= {LOW_STOCK}. "
        "Products link to suppliers through the 'suppliers' id list. Supplier phone numbers are personal "
        "data and are only returned when include_phone=true. Take numbers from the tools; never estimate."
    ),
)


@mcp.tool()
@_safe
def search_products(search: str | None = None, department: str | None = None, category: str | None = None,
                    product_type: str | None = None, supplier_id: int | None = None,
                    min_price: float | None = None, max_price: float | None = None,
                    limit: int = 20, skip: int = 0) -> dict:
    """List products (max 100), sorted by name. search matches name, sku, category, subCategory, colour.
    department is Women/Men/Kids. Each product includes total_units, low_stock and supplier_names."""
    q: dict = {}
    if department:
        q["department"] = {"$regex": f"^{re.escape(department)}$", "$options": "i"}
    if category:
        q["category"] = {"$regex": f"^{re.escape(category)}$", "$options": "i"}
    if product_type:
        q["type"] = {"$regex": f"^{re.escape(product_type)}$", "$options": "i"}
    if supplier_id is not None:
        q["suppliers"] = supplier_id
    if min_price is not None or max_price is not None:
        q["price"] = {k: v for k, v in (("$gte", min_price), ("$lte", max_price)) if v is not None}
    if search:
        rx = {"$regex": re.escape(search), "$options": "i"}
        q["$or"] = [{f: rx} for f in ("name", "sku", "category", "subCategory", "colour")]
    coll = _db()[PRODUCTS]
    names = _supplier_names()
    rows = coll.find(q).sort("name", 1).skip(max(skip, 0)).limit(max(1, min(limit, MAX_ROWS)))
    return {"matching": coll.count_documents(q),
            "products": _clean([_product_view(p, names) for p in rows])}


@mcp.tool()
@_safe
def get_product(product_id: int | None = None, sku: str | None = None) -> dict:
    """One product by id or sku, with resolved supplier names, total units and per-store stock."""
    if product_id is None and not sku:
        return {"error": "Pass product_id or sku"}
    q = {"_id": product_id} if product_id is not None else {"sku": sku}
    p = _db()[PRODUCTS].find_one(q)
    return _clean(_product_view(p, _supplier_names())) if p else {"error": "Product not found"}


@mcp.tool()
@_safe
def low_stock_products(threshold: int | None = None, department: str | None = None, limit: int = 50) -> dict:
    """Products whose total units (sum across stores) is at or below the threshold (default from config),
    lowest first, with per-store stock and suppliers so you can see who to reorder from."""
    t = LOW_STOCK if threshold is None else threshold
    match = {"department": {"$regex": f"^{re.escape(department)}$", "$options": "i"}} if department else {}
    rows = list(_db()[PRODUCTS].aggregate([
        {"$match": match}, {"$addFields": {"total_units": TOTAL_UNITS}},
        {"$match": {"total_units": {"$lte": t}}}, {"$sort": {"total_units": 1}},
        {"$limit": max(1, min(limit, MAX_ROWS))},
    ]))
    names = _supplier_names()
    return {"threshold": t, "products": _clean([_product_view(p, names) for p in rows])}


@mcp.tool()
@_safe
def inventory_summary(group_by: str = "department") -> dict:
    """Product count, total units and stock value (units x cost) and retail value (units x price), grouped by
    department, category, type or colour."""
    if group_by not in ("department", "category", "type", "colour"):
        return {"error": "group_by must be department, category, type or colour"}
    rows = list(_db()[PRODUCTS].aggregate([
        {"$addFields": {"u": TOTAL_UNITS}},
        {"$group": {"_id": f"${group_by}", "products": {"$sum": 1}, "units": {"$sum": "$u"},
                    "stock_cost_value": {"$sum": {"$multiply": ["$u", {"$ifNull": ["$cost", 0]}]}},
                    "stock_retail_value": {"$sum": {"$multiply": ["$u", {"$ifNull": ["$price", 0]}]}}}},
        {"$sort": {"units": -1}}, {"$limit": MAX_ROWS},
    ]))
    return {"group_by": group_by,
            "groups": [{group_by: r["_id"], **{k: v for k, v in r.items() if k != "_id"}} for r in _clean(rows)]}


@mcp.tool()
@_safe
def list_suppliers(search: str | None = None, include_phone: bool = False) -> dict:
    """All suppliers with id, name, product types and how many products reference each.
    Phone numbers are personal data: only set include_phone=true when the user asks for them."""
    q = {"name": {"$regex": re.escape(search), "$options": "i"}} if search else {}
    proj = {} if include_phone else {"phone": 0}
    sups = list(_db()[SUPPLIERS].find(q, proj).sort("name", 1))
    counts = {r["_id"]: r["n"] for r in _db()[PRODUCTS].aggregate(
        [{"$unwind": "$suppliers"}, {"$group": {"_id": "$suppliers", "n": {"$sum": 1}}}])}
    for s in sups:
        s["product_count"] = counts.get(s["_id"], 0)
    return {"suppliers": _clean(sups)}


@mcp.tool()
@_safe
def supplier_products(supplier_id: int, limit: int = 50) -> dict:
    """The supplier's details (without phone) and the products that reference it, with total units."""
    sup = _db()[SUPPLIERS].find_one({"_id": supplier_id}, {"phone": 0})
    if not sup:
        return {"error": f"No supplier with id {supplier_id}"}
    names = _supplier_names()
    rows = _db()[PRODUCTS].find({"suppliers": supplier_id}).sort("name", 1).limit(max(1, min(limit, MAX_ROWS)))
    return {"supplier": _clean(sup),
            "products": _clean([_product_view(p, names) for p in rows])}


if __name__ == "__main__":
    mcp.run()  # stdio, which is what Claude Desktop uses
