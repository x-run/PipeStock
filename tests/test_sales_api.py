"""Phase 4.5 tests — Sales event creation + Pie chart API.

Test IDs (SL-*) map to docs/TEST.md §4.5.
"""

import uuid
from datetime import date, datetime, timezone

from tests.helpers import create_item_id, post_sale


# ── POST /api/v1/sales ─────────────────────────────────────────────


class TestCreateSale:

    def test_sale_stores_positive_amount(self, client):
        """type=SALE → amount_yen stored as positive."""
        pid = create_item_id(client, code="SL-001", name="Sale Item")
        res = post_sale(client, amount_yen=5000, product_id=pid)
        assert res.status_code == 201
        data = res.json()["data"]
        assert data["type"] == "SALE"
        assert data["amount_yen"] == 5000
        assert data["product_id"] == pid

    def test_refund_stores_negative_amount(self, client):
        """type=REFUND → amount_yen stored as negative (server sign conversion)."""
        pid = create_item_id(client, code="SL-002", name="Refund Item")
        res = post_sale(
            client, type="REFUND", amount_yen=3000, product_id=pid, note="返品",
        )
        assert res.status_code == 201
        data = res.json()["data"]
        assert data["type"] == "REFUND"
        assert data["amount_yen"] == -3000

    def test_sale_without_product_id(self, client):
        """product_id=null is allowed (aggregated as UNKNOWN in pie)."""
        res = post_sale(client, amount_yen=1000)
        assert res.status_code == 201
        assert res.json()["data"]["product_id"] is None

    def test_sale_with_invalid_product_id(self, client):
        """Non-existent product_id → 404."""
        fake = str(uuid.uuid4())
        res = post_sale(client, amount_yen=1000, product_id=fake)
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "PRODUCT_NOT_FOUND"

    def test_request_id_duplicate(self, client):
        """Duplicate request_id → 409 DUPLICATE_REQUEST_ID."""
        rid = str(uuid.uuid4())
        res1 = post_sale(client, amount_yen=1000, request_id=rid)
        assert res1.status_code == 201

        res2 = post_sale(client, amount_yen=2000, request_id=rid)
        assert res2.status_code == 409
        assert res2.json()["error"]["code"] == "DUPLICATE_REQUEST_ID"

    def test_amount_yen_must_be_positive(self, client):
        """amount_yen < 1 → 400 validation error."""
        res = post_sale(client, amount_yen=0)
        assert res.status_code == 400

    def test_occurred_at_defaults_to_now(self, client):
        """Omitting occurred_at sets it server-side."""
        res = post_sale(client, amount_yen=1000)
        assert res.status_code == 201
        assert res.json()["data"]["occurred_at"] is not None


# ── GET /api/v1/dashboard/sales/pie ────────────────────────────────


def _seed_sales(client, date_prefix="2026-01-"):
    """Create 3 products with sales at known dates.

    Returns (a_id, b_id, c_id).
      A: 100000 yen
      B:  50000 yen
      C:  30000 yen
    Total: 180000 yen
    """
    a_id = create_item_id(client, code="PIE-A", name="Product A")
    b_id = create_item_id(client, code="PIE-B", name="Product B")
    c_id = create_item_id(client, code="PIE-C", name="Product C")

    post_sale(
        client, amount_yen=100000, product_id=a_id,
        occurred_at=f"{date_prefix}10T10:00:00",
    )
    post_sale(
        client, amount_yen=50000, product_id=b_id,
        occurred_at=f"{date_prefix}11T10:00:00",
    )
    post_sale(
        client, amount_yen=30000, product_id=c_id,
        occurred_at=f"{date_prefix}12T10:00:00",
    )
    return a_id, b_id, c_id


class TestSalesPie:

    def test_total_and_breakdown_by_product(self, client):
        """total_yen matches SUM, breakdown groups by product."""
        a_id, b_id, c_id = _seed_sales(client)

        res = client.get(
            "/api/v1/dashboard/sales/pie?start=2026-01-01&end=2026-01-31"
        )
        assert res.status_code == 200
        body = res.json()

        assert body["total_yen"] == 180000
        assert body["refund_total_yen"] == 0
        assert len(body["breakdown"]) == 3

        # Sorted by amount_yen DESC
        assert body["breakdown"][0]["key"] == a_id
        assert body["breakdown"][0]["amount_yen"] == 100000
        assert "PIE-A" in body["breakdown"][0]["label"]

    def test_refund_in_totals(self, client):
        """REFUND amounts appear negative in total and refund_total_yen."""
        pid = create_item_id(client, code="REF-P", name="Refund Product")
        post_sale(
            client, amount_yen=10000, product_id=pid,
            occurred_at="2026-03-05T10:00:00",
        )
        post_sale(
            client, type="REFUND", amount_yen=2000, product_id=pid,
            occurred_at="2026-03-06T10:00:00",
        )

        res = client.get(
            "/api/v1/dashboard/sales/pie?start=2026-03-01&end=2026-03-31"
        )
        body = res.json()
        assert body["total_yen"] == 8000  # 10000 - 2000
        assert body["refund_total_yen"] == -2000

    def test_limit_creates_other(self, client):
        """When products exceed limit, remaining are grouped as OTHER."""
        a_id, b_id, c_id = _seed_sales(client)

        res = client.get(
            "/api/v1/dashboard/sales/pie?start=2026-01-01&end=2026-01-31&limit=2"
        )
        body = res.json()

        assert len(body["breakdown"]) == 3  # 2 top + OTHER
        assert body["breakdown"][0]["key"] == a_id  # 100k
        assert body["breakdown"][1]["key"] == b_id  # 50k
        assert body["breakdown"][2]["key"] == "OTHER"
        assert body["breakdown"][2]["amount_yen"] == 30000  # C only

    def test_default_group_by_product(self, client):
        """group_by defaults to product; omitting it still works."""
        pid = create_item_id(client, code="DEF-P", name="Default Test")
        post_sale(
            client, amount_yen=5000, product_id=pid,
            occurred_at="2026-04-10T10:00:00",
        )

        # No group_by parameter
        res = client.get(
            "/api/v1/dashboard/sales/pie?start=2026-04-01&end=2026-04-30"
        )
        assert res.status_code == 200
        assert res.json()["breakdown"][0]["key"] == pid

    def test_null_product_becomes_unknown(self, client):
        """Sales with product_id=null are aggregated as UNKNOWN."""
        post_sale(
            client, amount_yen=7000,
            occurred_at="2026-05-10T10:00:00",
        )

        res = client.get(
            "/api/v1/dashboard/sales/pie?start=2026-05-01&end=2026-05-31"
        )
        body = res.json()
        unknown = next(b for b in body["breakdown"] if b["key"] == "UNKNOWN")
        assert unknown["amount_yen"] == 7000
        assert unknown["label"] == "不明な商品"

    def test_preset_month(self, client):
        """preset=month returns current month range and includes today's sales."""
        pid = create_item_id(client, code="PM-001", name="Preset Month")
        now = datetime.now(timezone.utc).isoformat()
        post_sale(client, amount_yen=10000, product_id=pid, occurred_at=now)

        res = client.get("/api/v1/dashboard/sales/pie?preset=month")
        body = res.json()

        today = date.today()
        assert body["range"]["preset"] == "month"
        assert body["range"]["start"] == today.replace(day=1).isoformat()
        assert body["range"]["end"] == today.isoformat()
        assert body["total_yen"] == 10000

    def test_custom_range(self, client):
        """Custom start/end takes precedence over preset."""
        pid = create_item_id(client, code="CR-001", name="Custom Range")
        post_sale(
            client, amount_yen=20000, product_id=pid,
            occurred_at="2026-06-15T10:00:00",
        )
        # Sale outside range
        post_sale(
            client, amount_yen=99999, product_id=pid,
            occurred_at="2026-07-01T10:00:00",
        )

        res = client.get(
            "/api/v1/dashboard/sales/pie?start=2026-06-01&end=2026-06-30"
        )
        body = res.json()
        assert body["range"]["preset"] is None
        assert body["total_yen"] == 20000  # only June sale

    def test_empty_period(self, client):
        """No sales in range → zero totals, empty breakdown."""
        res = client.get(
            "/api/v1/dashboard/sales/pie?start=2099-01-01&end=2099-01-31"
        )
        assert res.status_code == 200
        body = res.json()
        assert body["total_yen"] == 0
        assert body["refund_total_yen"] == 0
        assert body["breakdown"] == []
