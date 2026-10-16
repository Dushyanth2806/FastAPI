"""Read-only extraction queries for products, suppliers and purchase orders."""
import re

import config


def total_units(stock):
    return sum(v for v in (stock or {}).values() if isinstance(v, (int, float)))


def stock_status(units):
    if units <= 0:
        return "out_of_stock"
    if units <= config.LOW_STOCK_THRESHOLD:
        return "low_stock"
    return "in_stock"


def _supplier_names(db, ids):
    if not ids:
        return {}
    docs = db[config.SUPPLIERS_COLLECTION].find({"_id": {"$in": list(ids)}}, {"name": 1})
    return {d["_id"]: d.get("name") for d in docs}


def search_products(db, q=None, department=None, category=None, supplier_id=None,
                    low_stock_only=False, skip=0, limit=50):
    filt = {}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        filt["$or"] = [{"name": rx}, {"sku": rx}]
    if department:
        filt["department"] = department
    if category:
        filt["category"] = category
    if supplier_id is not None:
        filt["suppliers"] = supplier_id

    docs = list(db[config.PRODUCTS_COLLECTION].find(filt).sort("_id", 1))
    rows = []
    for d in docs:
        units = total_units(d.get("stock"))
        status = stock_status(units)
        if low_stock_only and status == "in_stock":
            continue
        d["total_units"] = units
        d["stock_status"] = status
        rows.append(d)

    total = len(rows)
    page = rows[skip:skip + limit]
    names = _supplier_names(db, {s for d in page for s in d.get("suppliers") or []})
    for d in page:
        d["supplier_names"] = [names.get(s) for s in d.get("suppliers") or []]
    return {"total": total, "items": page}


def list_suppliers(db):
    counts = {
        r["_id"]: r["n"]
        for r in db[config.PRODUCTS_COLLECTION].aggregate(
            [{"$unwind": "$suppliers"}, {"$group": {"_id": "$suppliers", "n": {"$sum": 1}}}]
        )
    }
    items = list(db[config.SUPPLIERS_COLLECTION].find().sort("_id", 1))
    for s in items:
        s["product_count"] = counts.get(s["_id"], 0)
    return {"total": len(items), "items": items}


def purchase_orders_available(db):
    return config.PURCHASE_ORDERS_COLLECTION in db.list_collection_names()


def list_purchase_orders(db, supplier_id=None, status=None, skip=0, limit=50):
    """Supplier orders from the `orders` collection. `phone` is PII and is excluded."""
    col = db[config.PURCHASE_ORDERS_COLLECTION]
    filt = {}
    if supplier_id is not None:
        filt["supplierId"] = supplier_id
    if status:
        filt["status"] = status
    items = list(col.find(filt, {"phone": 0}).sort("createdAt", -1).skip(skip).limit(limit))
    return {"total": col.count_documents(filt), "items": items}
