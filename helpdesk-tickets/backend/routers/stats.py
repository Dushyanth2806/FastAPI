"""Ticket statistics, computed from the real ticket records. Nulls are skipped, never counted as zero."""
from fastapi import APIRouter, Depends, Query

from database import get_tickets
from filters import ticket_filters

router = APIRouter(tags=["stats"])


def _by(field: str) -> list[dict]:
    return [{"$group": {"_id": field, "count": {"$sum": 1}}}, {"$sort": {"count": -1, "_id": 1}}]


def _rename(rows: list[dict]) -> list[dict]:
    return [{"name": r["_id"], "count": r["count"]} for r in rows]


@router.get("/stats")
def ticket_stats(
    flt: dict = Depends(ticket_filters),
    period: str = Query(default="day", pattern="^(day|week)$"),
    tickets=Depends(get_tickets),
):
    fmt = "%Y-%m-%d" if period == "day" else "%G-W%V"
    pipeline = [
        {"$match": flt},
        {"$facet": {
            "totals": [{"$group": {
                "_id": None,
                "total": {"$sum": 1},
                "latencyCount": {"$sum": {"$cond": [{"$isNumber": "$latency"}, 1, 0]}},
                "avgLatency": {"$avg": "$latency"},
                "maxLatency": {"$max": "$latency"},
                "costCount": {"$sum": {"$cond": [{"$isNumber": "$cost"}, 1, 0]}},
                "totalCost": {"$sum": "$cost"},
                "avgCost": {"$avg": "$cost"},
                "totalReplies": {"$sum": {"$size": {"$ifNull": ["$replies", []]}}},
                "noReply": {"$sum": {"$cond": [{"$eq": [{"$size": {"$ifNull": ["$replies", []]}}, 0]}, 1, 0]}},
            }}],
            "byDept": _by("$dept"),
            "byStore": _by("$store"),
            "byStaffRole": _by("$staffRole"),
            "byStatus": _by("$status"),
            "byPeriod": [
                {"$group": {"_id": {"$dateToString": {"format": fmt, "date": {"$toDate": "$createdAt"}}},
                            "count": {"$sum": 1}}},
                {"$sort": {"_id": 1}},
            ],
            "repliesDistribution": [
                {"$group": {"_id": {"$size": {"$ifNull": ["$replies", []]}}, "count": {"$sum": 1}}},
                {"$sort": {"_id": 1}},
            ],
        }},
    ]
    facets = next(iter(tickets.aggregate(pipeline)), {})
    totals = (facets.get("totals") or [{}])[0]
    totals.pop("_id", None)
    totals.setdefault("total", 0)
    totals.setdefault("totalReplies", 0)
    totals.setdefault("noReply", 0)
    return {
        "totals": totals,
        "period": period,
        "byDept": _rename(facets.get("byDept", [])),
        "byStore": _rename(facets.get("byStore", [])),
        "byStaffRole": _rename(facets.get("byStaffRole", [])),
        "byStatus": _rename(facets.get("byStatus", [])),
        "byPeriod": _rename(facets.get("byPeriod", [])),
        "repliesDistribution": [{"replies": r["_id"], "count": r["count"]} for r in facets.get("repliesDistribution", [])],
    }
