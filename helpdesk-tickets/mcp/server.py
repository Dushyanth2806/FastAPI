"""
Helpdesk connector for Claude Desktop (read-only).

Tools over neerus.tickets / neerus.departments / neerus.stores. Settings come from
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
TICKETS = os.getenv("COLLECTION_NAME", "tickets")
DEPARTMENTS = os.getenv("DEPARTMENTS_COLLECTION", "departments")
STORES = os.getenv("STORES_COLLECTION", "stores")
MAX_ROWS = 100

GROUP_FIELDS = {"dept": "$dept", "store": "$store", "staffRole": "$staffRole", "status": "$status",
                "staff": "$staff"}

_client = None


def _db():
    global _client
    if _client is None:
        if not MONGODB_URI or MONGODB_URI.startswith("your-"):
            raise RuntimeError("MONGODB_URI is not set in helpdesk-tickets/backend/.env")
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


def _filter(dept, store, status, staff_role, start_ms, end_ms, search):
    q = {}
    for field, val in (("dept", dept), ("store", store), ("status", status), ("staffRole", staff_role)):
        if val:
            q[field] = val
    if start_ms is not None or end_ms is not None:
        q["createdAt"] = {k: v for k, v in (("$gte", start_ms), ("$lte", end_ms)) if v is not None}
    if search:
        rx = {"$regex": re.escape(search), "$options": "i"}
        q["$or"] = [{"text": rx}, {"staff": rx}, {"store": rx}]
    return q


mcp = FastMCP(
    "helpdesk",
    instructions=(
        "Read-only tools for the helpdesk tickets in MongoDB (neerus.tickets). createdAt is epoch "
        "milliseconds. status is 'routed' on every ticket today. latency/cost are null on some tickets "
        "and their units are undocumented. Tickets contain staff names and free text: quote them only "
        "when needed and prefer ticket ids. Take numbers from the tools; never estimate."
    ),
)


@mcp.tool()
@_safe
def ticket_stats(group_by: str = "dept", dept: str | None = None, store: str | None = None,
                 status: str | None = None, staff_role: str | None = None,
                 start_ms: int | None = None, end_ms: int | None = None) -> dict:
    """Ticket counts grouped by one field (dept, store, staffRole, status or staff), plus overall totals:
    total tickets, average/max latency, total/average cost, tickets with no reply. Latency and cost
    ignore nulls. Optional filters; start_ms/end_ms are epoch milliseconds, inclusive."""
    if group_by not in GROUP_FIELDS:
        return {"error": f"group_by must be one of {sorted(GROUP_FIELDS)}"}
    match = {"$match": _filter(dept, store, status, staff_role, start_ms, end_ms, None)}
    coll = _db()[TICKETS]
    groups = list(coll.aggregate([
        match,
        {"$group": {"_id": GROUP_FIELDS[group_by], "tickets": {"$sum": 1},
                    "avg_latency": {"$avg": "$latency"}, "total_cost": {"$sum": "$cost"}}},
        {"$sort": {"tickets": -1}}, {"$limit": MAX_ROWS},
    ]))
    totals = next(coll.aggregate([match, {"$group": {
        "_id": None, "tickets": {"$sum": 1}, "avg_latency": {"$avg": "$latency"},
        "max_latency": {"$max": "$latency"}, "total_cost": {"$sum": "$cost"}, "avg_cost": {"$avg": "$cost"},
        "no_reply": {"$sum": {"$cond": [{"$eq": [{"$size": {"$ifNull": ["$replies", []]}}, 0]}, 1, 0]}},
    }}]), {})
    totals.pop("_id", None)
    return {"group_by": group_by,
            "groups": [{group_by: g["_id"], **{k: v for k, v in g.items() if k != "_id"}} for g in _clean(groups)],
            "totals": _clean(totals)}


@mcp.tool()
@_safe
def search_tickets(search: str | None = None, dept: str | None = None, store: str | None = None,
                   status: str | None = None, staff_role: str | None = None,
                   start_ms: int | None = None, end_ms: int | None = None,
                   limit: int = 20, skip: int = 0) -> dict:
    """List tickets, newest first (max 100). search matches ticket text, staff and store. Returns id, text,
    staff, staffRole, store, dept, status, createdAt, latency, cost and reply_count (not full replies)."""
    q = _filter(dept, store, status, staff_role, start_ms, end_ms, search)
    coll = _db()[TICKETS]
    limit = max(1, min(limit, MAX_ROWS))
    rows = list(coll.find(q, {"replies": 0}).sort("createdAt", -1).skip(max(skip, 0)).limit(limit))
    counts = {r["_id"]: r.get("n", 0) for r in coll.aggregate([
        {"$match": {"_id": {"$in": [r["_id"] for r in rows]}}},
        {"$project": {"n": {"$size": {"$ifNull": ["$replies", []]}}}}])}
    for r in rows:
        r["reply_count"] = counts.get(r["_id"], 0)
    return {"matching": coll.count_documents(q), "returned": len(rows), "tickets": _clean(rows)}


@mcp.tool()
@_safe
def get_ticket(ticket_id: int) -> dict:
    """One ticket by id, including the full reply thread."""
    doc = _db()[TICKETS].find_one({"_id": ticket_id})
    return _clean(doc) if doc else {"error": f"No ticket with id {ticket_id}"}


@mcp.tool()
@_safe
def list_departments_and_stores() -> dict:
    """Reference data: departments (name, handles, leader) and stores (name, hasLogin). Note that the
    'Corporate' department appears on tickets but has no department document."""
    db = _db()
    return {"departments": _clean(list(db[DEPARTMENTS].find({}))),
            "stores": _clean(list(db[STORES].find({}, {"staff": 0})))}


if __name__ == "__main__":
    mcp.run()  # stdio, which is what Claude Desktop uses
