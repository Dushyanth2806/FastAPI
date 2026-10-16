"""Unit tests for the shared filter builder (no database needed)."""
import pytest
from fastapi import HTTPException

from filters import ticket_filters


def build(**kw):
    defaults = dict(q=None, dept=None, store=None, status=None, staff_role=None, date_from=None, date_to=None)
    return ticket_filters(**{**defaults, **kw})


def test_empty_filter():
    assert build() == {}


def test_each_filter_maps_to_its_own_field():
    flt = build(dept="IT", store="Madhapur", status="routed", staff_role="Cashier")
    assert flt == {"dept": "IT", "store": "Madhapur", "status": "routed", "staffRole": "Cashier"}


def test_search_is_escaped_and_covers_three_fields():
    flt = build(q="a.b(")
    assert len(flt["$or"]) == 3
    assert flt["$or"][0]["text"]["$regex"] == r"a\.b\("


def test_date_range_is_inclusive():
    assert build(date_from=1.0, date_to=2.0)["createdAt"] == {"$gte": 1.0, "$lte": 2.0}


def test_reversed_date_range_rejected():
    with pytest.raises(HTTPException) as e:
        build(date_from=5.0, date_to=1.0)
    assert e.value.status_code == 422
