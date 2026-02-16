"""Tests — GET /api/v1/dashboard/stock/by-category.

Test IDs (SC-*) map to docs/TEST.md §4.3.
"""

from tests.helpers import create_item_id, post_tx


def _seed_categorised_items(client):
    """Create items whose names start with different categories.

    Categories (first token of name):
      ステンレスパイプ → category "ステンレスパイプ"
      銅パイプ         → category "銅パイプ"
      バルブ           → category "バルブ"

    Returns (pipe_s_id, pipe_c_id, valve_id).
    """
    pipe_s = create_item_id(
        client, code="SC-S01", name="ステンレスパイプ 25A", unit_price=2500,
    )
    pipe_c = create_item_id(
        client, code="SC-C01", name="銅パイプ 15A", unit_price=1500,
    )
    valve = create_item_id(
        client, code="SC-V01", name="バルブ ボール型", unit_price=5000,
    )

    # Stock: pipe_s=10, pipe_c=20, valve=5
    post_tx(client, pipe_s, type="IN", qty=10)
    post_tx(client, pipe_c, type="IN", qty=20)
    post_tx(client, valve, type="IN", qty=5)

    return pipe_s, pipe_c, valve


class TestStockByCategory:

    def test_default_metric_value(self, client):
        """SC-1: Default metric=value groups by category and sums on_hand*unit_price."""
        pipe_s, pipe_c, valve = _seed_categorised_items(client)

        res = client.get("/api/v1/dashboard/stock/by-category")
        assert res.status_code == 200
        body = res.json()

        assert body["metric"] == "value"
        # ステンレスパイプ: 10*2500=25000, 銅パイプ: 20*1500=30000, バルブ: 5*5000=25000
        assert body["total"] == 80000

        keys = [b["key"] for b in body["breakdown"]]
        assert "銅パイプ" in keys
        assert "ステンレスパイプ" in keys
        assert "バルブ" in keys

        # Sorted by value DESC → 銅パイプ(30000) first
        assert body["breakdown"][0]["key"] == "銅パイプ"
        assert body["breakdown"][0]["metric_value"] == 30000

    def test_metric_qty(self, client):
        """SC-2: metric=qty returns on_hand sums."""
        _seed_categorised_items(client)

        res = client.get("/api/v1/dashboard/stock/by-category?metric=qty")
        body = res.json()

        assert body["metric"] == "qty"
        assert body["total"] == 35  # 10+20+5

        # 銅パイプ(20) > ステンレスパイプ(10) > バルブ(5)
        assert body["breakdown"][0]["key"] == "銅パイプ"
        assert body["breakdown"][0]["metric_value"] == 20

    def test_metric_available(self, client):
        """SC-3: metric=available returns on_hand - reserved sums."""
        pipe_s, pipe_c, valve = _seed_categorised_items(client)

        # Reserve 3 from pipe_s → available = 10-3 = 7
        post_tx(client, pipe_s, type="RESERVE", qty=3)

        res = client.get("/api/v1/dashboard/stock/by-category?metric=available")
        body = res.json()

        assert body["metric"] == "available"
        assert body["total"] == 32  # 7+20+5

        cat_map = {b["key"]: b["metric_value"] for b in body["breakdown"]}
        assert cat_map["ステンレスパイプ"] == 7
        assert cat_map["銅パイプ"] == 20
        assert cat_map["バルブ"] == 5

    def test_metric_reserved(self, client):
        """SC-4: metric=reserved returns reserved_total sums."""
        pipe_s, pipe_c, valve = _seed_categorised_items(client)

        post_tx(client, pipe_s, type="RESERVE", qty=2)
        post_tx(client, pipe_c, type="RESERVE", qty=5)

        res = client.get("/api/v1/dashboard/stock/by-category?metric=reserved")
        body = res.json()

        assert body["metric"] == "reserved"
        assert body["total"] == 7  # 2+5

        cat_map = {b["key"]: b["metric_value"] for b in body["breakdown"]}
        assert cat_map["ステンレスパイプ"] == 2
        assert cat_map["銅パイプ"] == 5

    def test_same_category_aggregated(self, client):
        """SC-5: Multiple items with same first-word category are aggregated."""
        id1 = create_item_id(
            client, code="SC-AG1", name="ステンレスパイプ 25A", unit_price=2000,
        )
        id2 = create_item_id(
            client, code="SC-AG2", name="ステンレスパイプ 50A", unit_price=3000,
        )
        post_tx(client, id1, type="IN", qty=10)
        post_tx(client, id2, type="IN", qty=10)

        res = client.get("/api/v1/dashboard/stock/by-category?metric=value")
        body = res.json()

        cats = [b for b in body["breakdown"] if b["key"] == "ステンレスパイプ"]
        assert len(cats) == 1
        assert cats[0]["metric_value"] == 50000  # 10*2000 + 10*3000

    def test_fullwidth_space_split(self, client):
        """SC-6: Full-width space (U+3000) in name is handled as separator."""
        pid = create_item_id(
            client, code="SC-FW1", name="バルブ\u3000ゲート型", unit_price=4000,
        )
        post_tx(client, pid, type="IN", qty=5)

        res = client.get("/api/v1/dashboard/stock/by-category?metric=qty")
        body = res.json()

        cats = [b for b in body["breakdown"] if b["key"] == "バルブ"]
        assert len(cats) == 1
        assert cats[0]["metric_value"] == 5

    def test_limit_creates_other(self, client):
        """SC-7: When categories exceed limit, remaining are grouped as OTHER."""
        pipe_s, pipe_c, valve = _seed_categorised_items(client)

        res = client.get(
            "/api/v1/dashboard/stock/by-category?metric=qty&limit=2"
        )
        body = res.json()

        assert len(body["breakdown"]) == 3  # 2 top + OTHER
        assert body["breakdown"][0]["key"] == "銅パイプ"   # 20
        assert body["breakdown"][1]["key"] == "ステンレスパイプ"  # 10
        assert body["breakdown"][2]["key"] == "OTHER"
        assert body["breakdown"][2]["metric_value"] == 5   # バルブ

    def test_no_items(self, client):
        """SC-8: No items → total=0, empty breakdown."""
        res = client.get("/api/v1/dashboard/stock/by-category")
        assert res.status_code == 200
        body = res.json()
        assert body["total"] == 0
        assert body["breakdown"] == []

    def test_label_equals_key(self, client):
        """SC-9: label is the same as key (category name)."""
        pid = create_item_id(
            client, code="SC-LB1", name="ステンレスパイプ 25A", unit_price=1000,
        )
        post_tx(client, pid, type="IN", qty=1)

        res = client.get("/api/v1/dashboard/stock/by-category?metric=qty")
        body = res.json()

        item = body["breakdown"][0]
        assert item["key"] == item["label"] == "ステンレスパイプ"
