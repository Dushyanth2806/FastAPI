"""Shared ticket filters, used by both the list and the statistics endpoints."""
import re

from fastapi import HTTPException, Query


def ticket_filters(
    q: str | None = Query(default=None, max_length=100, description="Search text, staff and store"),
    dept: str | None = Query(default=None, max_length=50),
    store: str | None = Query(default=None, max_length=50),
    status: str | None = Query(default=None, max_length=50),
    staff_role: str | None = Query(default=None, max_length=50),
    date_from: float | None = Query(default=None, description="createdAt >= (epoch ms, inclusive)"),
    date_to: float | None = Query(default=None, description="createdAt <= (epoch ms, inclusive)"),
) -> dict:
    """Build a MongoDB filter. Every parameter has its own Query object."""
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(422, "date_from must not be after date_to.")
    flt: dict = {}
    if q:
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        flt["$or"] = [{"text": rx}, {"staff": rx}, {"store": rx}]
    for field, value in (("dept", dept), ("store", store), ("status", status), ("staffRole", staff_role)):
        if value:
            flt[field] = value
    if date_from is not None or date_to is not None:
        rng: dict = {}
        if date_from is not None:
            rng["$gte"] = date_from
        if date_to is not None:
            rng["$lte"] = date_to
        flt["createdAt"] = rng
    return flt
