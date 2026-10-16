"""Read-only ticket endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query

from database import get_departments, get_tickets
from filters import ticket_filters

router = APIRouter(tags=["tickets"])

LIST_FIELDS = {"text": 1, "staff": 1, "staffRole": 1, "store": 1, "dept": 1, "status": 1,
               "createdAt": 1, "latency": 1, "cost": 1, "kind": 1, "replyCount": {"$size": {"$ifNull": ["$replies", []]}}}


@router.get("/tickets")
def list_tickets(
    flt: dict = Depends(ticket_filters),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    sort: str = Query(default="desc", pattern="^(asc|desc)$"),
    tickets=Depends(get_tickets),
):
    """Tickets, newest first by default. The reply thread is only returned by the detail endpoint."""
    direction = 1 if sort == "asc" else -1
    items = list(tickets.aggregate([
        {"$match": flt},
        {"$sort": {"createdAt": direction, "_id": direction}},
        {"$skip": skip},
        {"$limit": limit},
        {"$project": LIST_FIELDS},
    ]))
    return {"total": tickets.count_documents(flt), "skip": skip, "limit": limit, "items": items}


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int, tickets=Depends(get_tickets)):
    doc = tickets.find_one({"_id": ticket_id})
    if doc is None:
        raise HTTPException(404, "Ticket not found.")
    return doc


@router.get("/filters")
def filter_options(tickets=Depends(get_tickets)):
    """Distinct values for the UI filter drop-downs, taken from the tickets themselves
    (not from departments: 'Corporate' is a ticket dept with no department document)."""
    return {f: sorted(v for v in tickets.distinct(f) if v) for f in ("dept", "store", "status", "staffRole")}


@router.get("/departments")
def list_departments(departments=Depends(get_departments)):
    return list(departments.find({}, {"name": 1, "handles": 1, "leader": 1}).sort("name", 1))
