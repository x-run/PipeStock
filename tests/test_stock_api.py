"""Phase 4 tests — Dashboard Stock Top API + Stock List API.

Test IDs (S-*) map to docs/TEST.md §4.
"""

from tests.helpers import create_item_id, post_batch, post_tx


# ── Helpers ─────────────────────────────────────────────────────────


def _seed_three_items(client):
    """Create 3 items with distinct on_hand and stock_value.

    Returns (a_id, b_id, c_id) where:
      A: on_hand=100, price=1000  → value=100_000
      B: on_hand=50,  price=5000  → value=250_000
      C: on_hand=200, price=200   → value= 40_000

    qty sort:   C(200) > A(100) > B(50)
    value sort: B(250k) > A(100k) > C(40k)
    """
    a_id = create_item_id(
        client, code="A-001", name="Item A", unit_price=1000, reorder_point=5,
    )
    post_tx(client, a_id, type="IN", qty=100)

    b_id = create_item_id(
        client, code="B-002", name="Item B", unit_price=5000, reorder_point=5,
    )
    post_tx(client, b_id, type="IN", qty=50)

    c_id = create_item_id(
        client, code="C-003", name="Item C", unit_price=200, reorder_point=5,
    )
    post_tx(client, c_id, type="IN", qty=200)

    return a_id, b_id, c_id


# ── Dashboard Stock Top ────────────────────────────────────────────


class TestDashboardStockTop:

    def test_top_qty_order_and_others(self, client):
        """Top N by on_hand DESC; others_total aggregates the rest."""
        _seed_three_items(client)

        res = client.get("/api/v1/dashboard/stock/top?metric=qty&limit=2")
        assert res.status_code == 200
        body = res.json()

        data = body["data"]
        assert len(data) == 2
        # C(200) > A(100)
        assert data[0]["code"] == "C-003"
        assert data[0]["on_hand"] == 200
        assert data[0]["stock_value"] == 200 * 200
        assert data[1]["code"] == "A-001"
        assert data[1]["on_hand"] == 100

        # others = B only
        others = body["others_total"]
        assert others["on_hand"] == 50
        assert others["stock_value"] == 50 * 5000
        assert others["available"] == 50

    def test_top_value_order(self, client):
        """Top N by stock_value (on_hand * unit_price) DESC."""
        _seed_three_items(client)

        res = client.get("/api/v1/dashboard/stock/top?metric=value&limit=2")
        assert res.status_code == 200
        data = res.json()["data"]

        # B(250k) > A(100k)
        assert data[0]["code"] == "B-002"
        assert data[0]["stock_value"] == 250_000
        assert data[1]["code"] == "A-001"
        assert data[1]["stock_value"] == 100_000

    def test_top_default_limit(self, client):
        """Default limit=10; fewer items → all in data, others empty."""
        _seed_three_items(client)

        res = client.get("/api/v1/dashboard/stock/top")
        assert res.status_code == 200
        body = res.json()
        assert len(body["data"]) == 3
        assert body["others_total"]["on_hand"] == 0

    def test_top_no_items(self, client):
        """No items → empty data, zero others."""
        res = client.get("/api/v1/dashboard/stock/top")
        assert res.status_code == 200
        body = res.json()
        assert body["data"] == []
        assert body["others_total"]["on_hand"] == 0

    def test_top_excludes_inactive(self, client):
        """Inactive items excluded by default."""
        a_id, b_id, c_id = _seed_three_items(client)

        # Deactivate C (highest on_hand)
        item = client.get(f"/api/v1/products/{c_id}").json()["data"]
        client.delete(f"/api/v1/products/{c_id}")

        res = client.get("/api/v1/dashboard/stock/top?metric=qty&limit=10")
        codes = [d["code"] for d in res.json()["data"]]
        assert "C-003" not in codes

        # include_inactive=true brings it back
        res = client.get(
            "/api/v1/dashboard/stock/top?metric=qty&limit=10&include_inactive=true"
        )
        codes = [d["code"] for d in res.json()["data"]]
        assert "C-003" in codes

    def test_pending_return_breakdown_in_top(self, client):
        """reserved_pending_return reflects RETURN_PENDING reason."""
        pid = create_item_id(
            client, code="RET-001", name="Return Item", reorder_point=0,
        )
        post_tx(client, pid, type="IN", qty=100)
        post_batch(client, pid, [
            {"type": "IN", "qty": 10, "reason": "RETURN_ARRIVED"},
            {"type": "RESERVE", "qty": 10, "reason": "RETURN_PENDING"},
        ])
        # Also a normal reserve
        post_tx(client, pid, type="RESERVE", qty=5, reason="ORDER")

        res = client.get("/api/v1/dashboard/stock/top?limit=20")
        assert res.status_code == 200
        item = res.json()["data"][0]
        assert item["on_hand"] == 110
        assert item["reserved_total"] == 15
        assert item["reserved_pending_return"] == 10
        assert item["reserved_pending_order"] == 0
        assert item["available"] == 95


# ── Stock List ─────────────────────────────────────────────────────


class TestStockList:

    def test_list_default(self, client):
        """Default listing returns items sorted by qty_desc."""
        _seed_three_items(client)

        res = client.get("/api/v1/stock")
        assert res.status_code == 200
        body = res.json()
        assert body["pagination"]["total"] == 3
        # qty_desc: C(200) > A(100) > B(50)
        codes = [d["code"] for d in body["data"]]
        assert codes == ["C-003", "A-001", "B-002"]

    def test_search_by_code(self, client):
        """q parameter filters by code partial match."""
        _seed_three_items(client)

        res = client.get("/api/v1/stock?q=B-002")
        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data) == 1
        assert data[0]["code"] == "B-002"

    def test_search_by_name(self, client):
        """q parameter filters by name partial match."""
        _seed_three_items(client)

        res = client.get("/api/v1/stock?q=Item A")
        data = res.json()["data"]
        assert len(data) == 1
        assert data[0]["code"] == "A-001"

    def test_sort_value_desc(self, client):
        """sort=value_desc orders by stock_value descending."""
        _seed_three_items(client)

        res = client.get("/api/v1/stock?sort=value_desc")
        codes = [d["code"] for d in res.json()["data"]]
        # B(250k) > A(100k) > C(40k)
        assert codes == ["B-002", "A-001", "C-003"]

    def test_sort_qty_asc(self, client):
        """sort=qty_asc orders by on_hand ascending."""
        _seed_three_items(client)

        res = client.get("/api/v1/stock?sort=qty_asc")
        codes = [d["code"] for d in res.json()["data"]]
        assert codes == ["B-002", "A-001", "C-003"]

    def test_pagination(self, client):
        """page/per_page limits results correctly."""
        _seed_three_items(client)

        res = client.get("/api/v1/stock?per_page=2&page=1&sort=qty_desc")
        body = res.json()
        assert len(body["data"]) == 2
        assert body["pagination"]["total"] == 3
        assert body["data"][0]["code"] == "C-003"

        res = client.get("/api/v1/stock?per_page=2&page=2&sort=qty_desc")
        body = res.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["code"] == "B-002"

    def test_needs_reorder_flag(self, client):
        """needs_reorder is true when available <= reorder_point."""
        # reorder_point=50, on_hand=50, available=50 → needs_reorder=true (<=)
        pid = create_item_id(
            client, code="REORDER", name="Low Stock", reorder_point=50,
        )
        post_tx(client, pid, type="IN", qty=50)

        res = client.get("/api/v1/stock")
        item = next(d for d in res.json()["data"] if d["code"] == "REORDER")
        assert item["needs_reorder"] is True
        assert item["available"] == 50

    def test_needs_reorder_false(self, client):
        """needs_reorder is false when available > reorder_point."""
        pid = create_item_id(
            client, code="ENOUGH", name="Enough Stock", reorder_point=10,
        )
        post_tx(client, pid, type="IN", qty=100)

        res = client.get("/api/v1/stock")
        item = next(d for d in res.json()["data"] if d["code"] == "ENOUGH")
        assert item["needs_reorder"] is False

    def test_pending_return_breakdown(self, client):
        """RETURN_PENDING reason is split into reserved_pending_return."""
        pid = create_item_id(
            client, code="RET", name="Return Test", reorder_point=0,
        )
        post_tx(client, pid, type="IN", qty=100)
        post_batch(client, pid, [
            {"type": "IN", "qty": 10, "reason": "RETURN_ARRIVED"},
            {"type": "RESERVE", "qty": 10, "reason": "RETURN_PENDING"},
        ])
        post_tx(client, pid, type="RESERVE", qty=5, reason="ORDER")

        res = client.get("/api/v1/stock")
        item = next(d for d in res.json()["data"] if d["code"] == "RET")
        assert item["on_hand"] == 110
        assert item["reserved_total"] == 15
        assert item["reserved_pending_return"] == 10
        assert item["reserved_pending_order"] == 0
        assert item["available"] == 95
        assert item["stock_value"] == 110 * 2500  # default unit_price

    def test_item_with_no_transactions(self, client):
        """Item with zero transactions shows all-zero stock."""
        create_item_id(client, code="EMPTY", name="No Tx")

        res = client.get("/api/v1/stock")
        item = next(d for d in res.json()["data"] if d["code"] == "EMPTY")
        assert item["on_hand"] == 0
        assert item["reserved_total"] == 0
        assert item["available"] == 0
        assert item["stock_value"] == 0

    def test_excludes_inactive(self, client):
        """Inactive items hidden by default, shown with include_inactive."""
        pid = create_item_id(client, code="DEL", name="To Delete")
        post_tx(client, pid, type="IN", qty=10)
        client.delete(f"/api/v1/products/{pid}")

        res = client.get("/api/v1/stock")
        codes = [d["code"] for d in res.json()["data"]]
        assert "DEL" not in codes

        res = client.get("/api/v1/stock?include_inactive=true")
        codes = [d["code"] for d in res.json()["data"]]
        assert "DEL" in codes
