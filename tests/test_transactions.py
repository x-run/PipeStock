"""Phase 3 tests — Transaction API + invariant validation.

Test IDs (T-*) map to docs/TEST.md §3.
"""

import uuid


# ── helpers ──────────────────────────────────────────────────────

def _create_item(client, **overrides) -> str:
    """Create an item and return its id."""
    payload = {
        "code": "PIPE-001",
        "name": "ステンレスパイプ 25A",
        "spec": "SUS304",
        "unit": "本",
        "unit_price": 2500,
        "unit_weight": 3.2,
        "reorder_point": 10,
    }
    payload.update(overrides)
    res = client.post("/api/v1/products", json=payload)
    assert res.status_code == 201
    return res.json()["data"]["id"]


def _post_tx(client, item_id, **kw):
    """POST a single transaction."""
    payload = {"type": "IN", "bucket": "ON_HAND", "qty_delta": 1, "reason": None}
    payload.update(kw)
    return client.post(f"/api/v1/products/{item_id}/transactions", json=payload)


def _post_batch(client, item_id, txs):
    """POST a batch of transactions."""
    return client.post(
        f"/api/v1/products/{item_id}/transactions/batch",
        json={"transactions": txs},
    )


# ── T-1 ~ T-8: normal cases ─────────────────────────────────────

class TestTxNormal:
    def test_t1_in_on_hand(self, client):
        """IN / ON_HAND → On-hand increases."""
        pid = _create_item(client)
        res = _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=50)
        assert res.status_code == 201
        stock = res.json()["stock"]
        assert stock["on_hand"] == 50
        assert stock["reserved"] == 0
        assert stock["available"] == 50

    def test_t2_out_on_hand(self, client):
        """OUT / ON_HAND (Available sufficient) → On-hand decreases."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=100)
        res = _post_tx(client, pid, type="OUT", bucket="ON_HAND", qty_delta=-30)
        assert res.status_code == 201
        stock = res.json()["stock"]
        assert stock["on_hand"] == 70
        assert stock["available"] == 70

    def test_t3_in_reserved(self, client):
        """IN / RESERVED → Reserved increases, Available decreases."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=100)
        res = _post_tx(client, pid, type="IN", bucket="RESERVED", qty_delta=20)
        assert res.status_code == 201
        stock = res.json()["stock"]
        assert stock["on_hand"] == 100
        assert stock["reserved"] == 20
        assert stock["available"] == 80

    def test_t4_out_reserved(self, client):
        """OUT / RESERVED → Reserved decreases, Available increases."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=100)
        _post_tx(client, pid, type="IN", bucket="RESERVED", qty_delta=30)
        res = _post_tx(client, pid, type="OUT", bucket="RESERVED", qty_delta=-10)
        assert res.status_code == 201
        stock = res.json()["stock"]
        assert stock["reserved"] == 20
        assert stock["available"] == 80

    def test_t5_adjust_increase(self, client):
        """ADJUST / ON_HAND (increase) → On-hand increases."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=50)
        res = _post_tx(client, pid, type="ADJUST", bucket="ON_HAND", qty_delta=5)
        assert res.status_code == 201
        assert res.json()["stock"]["on_hand"] == 55

    def test_t6_adjust_decrease(self, client):
        """ADJUST / ON_HAND (decrease) → On-hand decreases."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=50)
        res = _post_tx(client, pid, type="ADJUST", bucket="ON_HAND", qty_delta=-2)
        assert res.status_code == 201
        assert res.json()["stock"]["on_hand"] == 48

    def test_t7_multiple_txs_sum(self, client):
        """Multiple Txs → SUM aggregation is correct."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=100)
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=50)
        _post_tx(client, pid, type="OUT", bucket="ON_HAND", qty_delta=-30)
        _post_tx(client, pid, type="IN", bucket="RESERVED", qty_delta=20)
        res = _post_tx(client, pid, type="OUT", bucket="RESERVED", qty_delta=-5)
        stock = res.json()["stock"]
        assert stock["on_hand"] == 120   # 100+50-30
        assert stock["reserved"] == 15   # 20-5
        assert stock["available"] == 105  # 120-15

    def test_t8_history_newest_first(self, client):
        """Tx history → returned in newest-first order."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=10, reason="1st")
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=20, reason="2nd")
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=30, reason="3rd")

        res = client.get(f"/api/v1/products/{pid}/transactions")
        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data) == 3
        assert data[0]["reason"] == "3rd"
        assert data[2]["reason"] == "1st"


# ── T-9 ~ T-20: invariant violations ────────────────────────────

class TestTxInvariants:
    # INV-3  OUT/ON_HAND
    def test_t9_out_insufficient_available(self, client):
        """Available insufficient for OUT → 409."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=10)
        res = _post_tx(client, pid, type="OUT", bucket="ON_HAND", qty_delta=-20)
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "INSUFFICIENT_AVAILABLE"

    def test_t10_out_exact_boundary(self, client):
        """Available exactly sufficient → success (boundary)."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=10)
        res = _post_tx(client, pid, type="OUT", bucket="ON_HAND", qty_delta=-10)
        assert res.status_code == 201
        assert res.json()["stock"]["available"] == 0

    def test_t11_out_at_zero(self, client):
        """Available=0, OUT qty=1 → 409."""
        pid = _create_item(client)
        res = _post_tx(client, pid, type="OUT", bucket="ON_HAND", qty_delta=-1)
        assert res.status_code == 409

    # INV-6
    def test_t12_adjust_reserved(self, client):
        """ADJUST / RESERVED → 400."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=10)
        res = _post_tx(client, pid, type="ADJUST", bucket="RESERVED", qty_delta=5)
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "VALIDATION_ERROR"

    # INV-7
    def test_t13_qty_delta_zero(self, client):
        """qty_delta=0 → 400."""
        pid = _create_item(client)
        res = _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=0)
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "VALIDATION_ERROR"

    # INV-8
    def test_t14_inactive_item(self, client):
        """Tx on inactive item → 400 PRODUCT_INACTIVE."""
        pid = _create_item(client)
        client.delete(f"/api/v1/products/{pid}")
        res = _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=5)
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "PRODUCT_INACTIVE"

    # INV-1
    def test_t15_on_hand_negative(self, client):
        """Operation that would make On-hand negative → error."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=5)
        res = _post_tx(client, pid, type="ADJUST", bucket="ON_HAND", qty_delta=-10)
        assert res.status_code == 409

    # INV-2
    def test_t16_reserved_negative(self, client):
        """Operation that would make Reserved negative → error."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=10)
        res = _post_tx(client, pid, type="OUT", bucket="RESERVED", qty_delta=-1)
        assert res.status_code == 409

    # INV-5
    def test_t17_tx_update_not_allowed(self, client):
        """Tx update → no endpoint (405 or 404)."""
        pid = _create_item(client)
        res = _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=10)
        tx_id = res.json()["data"]["id"]
        res = client.put(
            f"/api/v1/products/{pid}/transactions/{tx_id}",
            json={"qty_delta": 99},
        )
        assert res.status_code in (404, 405)

    def test_t18_tx_delete_not_allowed(self, client):
        """Tx delete → no endpoint (405 or 404)."""
        pid = _create_item(client)
        res = _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=10)
        tx_id = res.json()["data"]["id"]
        res = client.delete(f"/api/v1/products/{pid}/transactions/{tx_id}")
        assert res.status_code in (404, 405)

    # INV-3  IN/RESERVED (引当で Available 超過)
    def test_t19_reserve_exceeds_available(self, client):
        """Available exceeded by reservation → 409."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=10)
        res = _post_tx(client, pid, type="IN", bucket="RESERVED", qty_delta=20)
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "INSUFFICIENT_AVAILABLE"

    def test_t20_reserve_exact_boundary(self, client):
        """Available exactly sufficient for reservation → success."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=10)
        res = _post_tx(client, pid, type="IN", bucket="RESERVED", qty_delta=10)
        assert res.status_code == 201
        assert res.json()["stock"]["available"] == 0

    def test_adjust_decreases_available_check(self, client):
        """ADJUST that would make Available negative → 409."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=10)
        _post_tx(client, pid, type="IN", bucket="RESERVED", qty_delta=8)
        # available=2, adjust -5 would make on_hand=5, available=-3
        res = _post_tx(client, pid, type="ADJUST", bucket="ON_HAND", qty_delta=-5)
        assert res.status_code == 409


# ── Batch endpoint ───────────────────────────────────────────────

class TestBatchTx:
    def test_shipment_batch(self, client):
        """引当解除・出荷: OUT/ON_HAND + OUT/RESERVED atomically."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=100)
        _post_tx(client, pid, type="IN", bucket="RESERVED", qty_delta=30)

        res = _post_batch(client, pid, [
            {"type": "OUT", "bucket": "ON_HAND", "qty_delta": -30},
            {"type": "OUT", "bucket": "RESERVED", "qty_delta": -30},
        ])
        assert res.status_code == 201
        assert len(res.json()["data"]) == 2
        stock = res.json()["stock"]
        assert stock["on_hand"] == 70
        assert stock["reserved"] == 0
        assert stock["available"] == 70

    def test_batch_all_or_nothing(self, client):
        """If batch would violate invariant, nothing is committed."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=10)

        # second tx would make on_hand=-90 total
        res = _post_batch(client, pid, [
            {"type": "OUT", "bucket": "ON_HAND", "qty_delta": -5},
            {"type": "OUT", "bucket": "ON_HAND", "qty_delta": -100},
        ])
        assert res.status_code == 409

        # verify nothing was persisted
        history = client.get(f"/api/v1/products/{pid}/transactions")
        assert history.json()["pagination"]["total"] == 1  # only the IN

    def test_batch_validates_after_sum(self, client):
        """Batch invariants are checked on the SUM, not intermediate."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=10)
        _post_tx(client, pid, type="IN", bucket="RESERVED", qty_delta=10)
        # available=0.  Ship 5: ON_HAND-5, RESERVED-5 → available still 0. OK.
        res = _post_batch(client, pid, [
            {"type": "OUT", "bucket": "ON_HAND", "qty_delta": -5},
            {"type": "OUT", "bucket": "RESERVED", "qty_delta": -5},
        ])
        assert res.status_code == 201
        assert res.json()["stock"]["available"] == 0

    def test_batch_inactive_item(self, client):
        pid = _create_item(client)
        client.delete(f"/api/v1/products/{pid}")
        res = _post_batch(client, pid, [
            {"type": "IN", "bucket": "ON_HAND", "qty_delta": 10},
        ])
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "PRODUCT_INACTIVE"


# ── Tx history filters / pagination ──────────────────────────────

class TestTxHistory:
    def test_filter_by_type(self, client):
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=50)
        _post_tx(client, pid, type="OUT", bucket="ON_HAND", qty_delta=-10)

        res = client.get(f"/api/v1/products/{pid}/transactions?type=IN")
        assert res.json()["pagination"]["total"] == 1
        assert res.json()["data"][0]["type"] == "IN"

    def test_filter_by_bucket(self, client):
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=50)
        _post_tx(client, pid, type="IN", bucket="RESERVED", qty_delta=10)

        res = client.get(f"/api/v1/products/{pid}/transactions?bucket=RESERVED")
        assert res.json()["pagination"]["total"] == 1
        assert res.json()["data"][0]["bucket"] == "RESERVED"

    def test_pagination(self, client):
        pid = _create_item(client)
        for i in range(5):
            _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=1)

        res = client.get(f"/api/v1/products/{pid}/transactions?per_page=2&page=1")
        body = res.json()
        assert len(body["data"]) == 2
        assert body["pagination"]["total"] == 5

    def test_product_not_found(self, client):
        fake = uuid.uuid4()
        res = client.get(f"/api/v1/products/{fake}/transactions")
        assert res.status_code == 404


# ── Response shape ───────────────────────────────────────────────

class TestTxResponseShape:
    def test_single_tx_response_fields(self, client):
        pid = _create_item(client)
        res = _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=10, reason="入荷")
        assert res.status_code == 201
        data = res.json()["data"]
        assert data["product_id"] == pid
        assert data["type"] == "IN"
        assert data["bucket"] == "ON_HAND"
        assert data["qty_delta"] == 10
        assert data["reason"] == "入荷"
        assert "id" in data
        assert "created_at" in data

    def test_stock_zero_before_any_tx(self, client):
        """Brand-new item with no Tx → stock is all zeros."""
        pid = _create_item(client)
        # Use a trick: create a +1 then -1 to see stock returns to 0
        _post_tx(client, pid, type="IN", bucket="ON_HAND", qty_delta=1)
        res = _post_tx(client, pid, type="OUT", bucket="ON_HAND", qty_delta=-1)
        stock = res.json()["stock"]
        assert stock == {"available": 0, "on_hand": 0, "reserved": 0}
