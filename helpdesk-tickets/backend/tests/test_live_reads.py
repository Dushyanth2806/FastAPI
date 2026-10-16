"""Read-only tests against the live Atlas collection. Skipped without MONGODB_URI. Nothing is written."""
import os

import pytest
from fastapi.testclient import TestClient

from config import get_settings

pytestmark = pytest.mark.skipif(
    not get_settings().mongodb_uri or get_settings().mongodb_uri.startswith("your-"),
    reason="MONGODB_URI not configured",
)


@pytest.fixture(scope="module")
def client():
    from main import app
    return TestClient(app)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["tickets"] > 0


def test_list_pagination_and_order(client):
    r = client.get("/api/tickets", params={"limit": 5})
    body = r.json()
    assert r.status_code == 200 and len(body["items"]) == 5
    times = [t["createdAt"] for t in body["items"]]
    assert times == sorted(times, reverse=True)
    assert "replies" not in body["items"][0] and "replyCount" in body["items"][0]


def test_limit_is_capped(client):
    assert client.get("/api/tickets", params={"limit": 101}).status_code == 422


def test_department_filter_actually_filters(client):
    total = client.get("/api/tickets", params={"limit": 1}).json()["total"]
    it = client.get("/api/tickets", params={"dept": "IT", "limit": 100}).json()
    assert 0 < it["total"] < total
    assert all(t["dept"] == "IT" for t in it["items"])


def test_filters_combine_independently(client):
    store = client.get("/api/tickets", params={"store": "Madhapur", "limit": 100}).json()
    both = client.get("/api/tickets", params={"store": "Madhapur", "dept": "IT", "limit": 100}).json()
    assert both["total"] <= store["total"]
    assert all(t["store"] == "Madhapur" and t["dept"] == "IT" for t in both["items"])


def test_detail_has_reply_thread_and_404(client):
    first = client.get("/api/tickets", params={"limit": 1}).json()["items"][0]
    detail = client.get(f"/api/tickets/{first['_id']}").json()
    assert isinstance(detail["replies"], list)
    assert client.get("/api/tickets/-1").status_code == 404


def test_stats_are_consistent(client):
    s = client.get("/api/stats").json()
    total = s["totals"]["total"]
    for key in ("byDept", "byStore", "byStaffRole", "byStatus", "byPeriod"):
        assert sum(r["count"] for r in s[key]) == total, key
    assert sum(r["count"] for r in s["repliesDistribution"]) == total
    t = s["totals"]
    assert t["latencyCount"] < total  # nulls are skipped, not counted as zero
    assert t["maxLatency"] >= t["avgLatency"] > 0
    assert t["noReply"] == next((r["count"] for r in s["repliesDistribution"] if r["replies"] == 0), 0)


def test_stats_respect_filters_and_week(client):
    s = client.get("/api/stats", params={"dept": "IT", "period": "week"}).json()
    assert s["byDept"] == [{"name": "IT", "count": s["totals"]["total"]}]
    assert "-W" in s["byPeriod"][0]["name"]


def test_filter_options_and_departments(client):
    opts = client.get("/api/filters").json()
    assert "Corporate" in opts["dept"]  # tickets use it although it has no department document
    assert len(client.get("/api/departments").json()) == 8
