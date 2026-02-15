"""Phase 3 tests — Transaction API + invariant validation.

Test IDs (T-*) map to docs/TEST.md §3.
Updated for safe-API design: qty (positive) + type determines sign & bucket.
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
    """POST a single transaction with the new safe API shape."""
    payload = {"type": "IN", "qty": 1}
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
    def test_t1_in(self, client):
        """IN → On-hand increases."""
        pid = _create_item(client)
        res = _post_tx(client, pid, type="IN", qty=50)
        assert res.status_code == 201
        stock = res.json()["stock"]
        assert stock["on_hand"] == 50
        assert stock["reserved"] == 0
        assert stock["available"] == 50

    def test_t2_out(self, client):
        """OUT (Available sufficient) → On-hand decreases."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=100)
        res = _post_tx(client, pid, type="OUT", qty=30)
        assert res.status_code == 201
        stock = res.json()["stock"]
        assert stock["on_hand"] == 70
        assert stock["available"] == 70

    def test_t3_reserve(self, client):
        """RESERVE → Reserved increases, Available decreases."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=100)
        res = _post_tx(client, pid, type="RESERVE", qty=20)
        assert res.status_code == 201
        stock = res.json()["stock"]
        assert stock["on_hand"] == 100
        assert stock["reserved"] == 20
        assert stock["available"] == 80

    def test_t4_unreserve(self, client):
        """UNRESERVE → Reserved decreases, Available increases."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=100)
        _post_tx(client, pid, type="RESERVE", qty=30)
        res = _post_tx(client, pid, type="UNRESERVE", qty=10)
        assert res.status_code == 201
        stock = res.json()["stock"]
        assert stock["reserved"] == 20
        assert stock["available"] == 80

    def test_t5_adjust_increase(self, client):
        """ADJUST/INCREASE → On-hand increases."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=50)
        res = _post_tx(client, pid, type="ADJUST", qty=5, direction="INCREASE")
        assert res.status_code == 201
        assert res.json()["stock"]["on_hand"] == 55

    def test_t6_adjust_decrease(self, client):
        """ADJUST/DECREASE → On-hand decreases."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=50)
        res = _post_tx(client, pid, type="ADJUST", qty=2, direction="DECREASE")
        assert res.status_code == 201
        assert res.json()["stock"]["on_hand"] == 48

    def test_t7_multiple_txs_sum(self, client):
        """Multiple Txs → SUM aggregation is correct."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=100)
        _post_tx(client, pid, type="IN", qty=50)
        _post_tx(client, pid, type="OUT", qty=30)
        _post_tx(client, pid, type="RESERVE", qty=20)
        res = _post_tx(client, pid, type="UNRESERVE", qty=5)
        stock = res.json()["stock"]
        assert stock["on_hand"] == 120   # 100+50-30
        assert stock["reserved"] == 15   # 20-5
        assert stock["available"] == 105  # 120-15

    def test_t8_history_newest_first(self, client):
        """Tx history → returned in newest-first order."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=10, reason="1st")
        _post_tx(client, pid, type="IN", qty=20, reason="2nd")
        _post_tx(client, pid, type="IN", qty=30, reason="3rd")

        res = client.get(f"/api/v1/products/{pid}/transactions")
        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data) == 3
        assert data[0]["reason"] == "3rd"
        assert data[2]["reason"] == "1st"


# ── T-9 ~ T-20: invariant violations ────────────────────────────

class TestTxInvariants:
    # INV-3  OUT (Available不足, On-handは正)
    def test_t9_out_insufficient_available(self, client):
        """Available insufficient for OUT (on_hand OK, reserved constrains) → 409."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=10)
        _post_tx(client, pid, type="RESERVE", qty=8)
        # on_hand=10, reserved=8, available=2 → OUT qty=5 makes available=-3
        res = _post_tx(client, pid, type="OUT", qty=5)
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "INSUFFICIENT_AVAILABLE"

    def test_t10_out_exact_boundary(self, client):
        """Available exactly sufficient → success (boundary)."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=10)
        res = _post_tx(client, pid, type="OUT", qty=10)
        assert res.status_code == 201
        assert res.json()["stock"]["available"] == 0

    def test_t11_out_at_zero(self, client):
        """Available=0, OUT qty=1 → 409."""
        pid = _create_item(client)
        res = _post_tx(client, pid, type="OUT", qty=1)
        assert res.status_code == 409

    # INV-6 (now enforced by schema: ADJUST bucket is always ON_HAND)
    def test_t12_adjust_without_direction(self, client):
        """ADJUST without direction → 400."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=10)
        res = _post_tx(client, pid, type="ADJUST", qty=5)
        assert res.status_code == 400

    # INV-7 (qty >= 1 enforced by schema)
    def test_t13_qty_zero(self, client):
        """qty=0 → 400."""
        pid = _create_item(client)
        res = _post_tx(client, pid, type="IN", qty=0)
        assert res.status_code == 400

    # INV-8
    def test_t14_inactive_item(self, client):
        """Tx on inactive item → 400 PRODUCT_INACTIVE."""
        pid = _create_item(client)
        client.delete(f"/api/v1/products/{pid}")
        res = _post_tx(client, pid, type="IN", qty=5)
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "PRODUCT_INACTIVE"

    # INV-1
    def test_t15_on_hand_negative(self, client):
        """Operation that would make On-hand negative → 409 INSUFFICIENT_ON_HAND."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=5)
        res = _post_tx(client, pid, type="ADJUST", qty=10, direction="DECREASE")
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "INSUFFICIENT_ON_HAND"

    # INV-2
    def test_t16_reserved_negative(self, client):
        """Operation that would make Reserved negative → 409 INSUFFICIENT_RESERVED."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=10)
        res = _post_tx(client, pid, type="UNRESERVE", qty=1)
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "INSUFFICIENT_RESERVED"

    # INV-5
    def test_t17_tx_update_not_allowed(self, client):
        """Tx update → no endpoint (405 or 404)."""
        pid = _create_item(client)
        res = _post_tx(client, pid, type="IN", qty=10)
        tx_id = res.json()["data"]["id"]
        res = client.put(
            f"/api/v1/products/{pid}/transactions/{tx_id}",
            json={"qty": 99},
        )
        assert res.status_code in (404, 405)

    def test_t18_tx_delete_not_allowed(self, client):
        """Tx delete → no endpoint (405 or 404)."""
        pid = _create_item(client)
        res = _post_tx(client, pid, type="IN", qty=10)
        tx_id = res.json()["data"]["id"]
        res = client.delete(f"/api/v1/products/{pid}/transactions/{tx_id}")
        assert res.status_code in (404, 405)

    # INV-3  RESERVE (引当で Available 超過)
    def test_t19_reserve_exceeds_available(self, client):
        """Available exceeded by reservation → 409."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=10)
        res = _post_tx(client, pid, type="RESERVE", qty=20)
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "INSUFFICIENT_AVAILABLE"

    def test_t20_reserve_exact_boundary(self, client):
        """Available exactly sufficient for reservation → success."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=10)
        res = _post_tx(client, pid, type="RESERVE", qty=10)
        assert res.status_code == 201
        assert res.json()["stock"]["available"] == 0

    def test_adjust_decrease_available_check(self, client):
        """ADJUST/DECREASE that would make Available negative → 409."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=10)
        _post_tx(client, pid, type="RESERVE", qty=8)
        # available=2, adjust decrease 5 → on_hand=5, available=-3
        res = _post_tx(client, pid, type="ADJUST", qty=5, direction="DECREASE")
        assert res.status_code == 409


# ── Batch endpoint ───────────────────────────────────────────────

class TestBatchTx:
    def test_shipment_batch(self, client):
        """引当解除・出荷: OUT + UNRESERVE atomically."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=100)
        _post_tx(client, pid, type="RESERVE", qty=30)

        res = _post_batch(client, pid, [
            {"type": "OUT", "qty": 30},
            {"type": "UNRESERVE", "qty": 30},
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
        _post_tx(client, pid, type="IN", qty=10)

        # total OUT=105 would make on_hand=-95
        res = _post_batch(client, pid, [
            {"type": "OUT", "qty": 5},
            {"type": "OUT", "qty": 100},
        ])
        assert res.status_code == 409

        # verify nothing was persisted
        history = client.get(f"/api/v1/products/{pid}/transactions")
        assert history.json()["pagination"]["total"] == 1  # only the IN

    def test_batch_validates_after_sum(self, client):
        """Batch invariants are checked on the SUM, not intermediate."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=10)
        _post_tx(client, pid, type="RESERVE", qty=10)
        # available=0. Ship 5: OUT 5 + UNRESERVE 5 → available still 0. OK.
        res = _post_batch(client, pid, [
            {"type": "OUT", "qty": 5},
            {"type": "UNRESERVE", "qty": 5},
        ])
        assert res.status_code == 201
        assert res.json()["stock"]["available"] == 0

    def test_batch_inactive_item(self, client):
        pid = _create_item(client)
        client.delete(f"/api/v1/products/{pid}")
        res = _post_batch(client, pid, [
            {"type": "IN", "qty": 10},
        ])
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "PRODUCT_INACTIVE"

    def test_batch_request_id_dup_external(self, client):
        """Batch with request_id already in DB → entire batch rolls back."""
        pid = _create_item(client)
        dup_rid = str(uuid.uuid4())

        # Seed: one tx with a specific request_id
        res = _post_tx(client, pid, type="IN", qty=50, request_id=dup_rid)
        assert res.status_code == 201

        # Batch where second tx reuses the same request_id
        res = _post_batch(client, pid, [
            {"type": "IN", "qty": 10, "request_id": str(uuid.uuid4())},
            {"type": "IN", "qty": 20, "request_id": dup_rid},
        ])
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "DUPLICATE_REQUEST_ID"

        # Nothing from the batch was persisted (all-or-nothing)
        history = client.get(f"/api/v1/products/{pid}/transactions")
        assert history.json()["pagination"]["total"] == 1  # only the seed

    def test_batch_request_id_dup_within(self, client):
        """Batch with duplicate request_ids within same batch → all-or-nothing."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=50)

        same_rid = str(uuid.uuid4())
        res = _post_batch(client, pid, [
            {"type": "OUT", "qty": 5, "request_id": same_rid},
            {"type": "OUT", "qty": 3, "request_id": same_rid},
        ])
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "DUPLICATE_REQUEST_ID"

        # Nothing from the batch was persisted
        history = client.get(f"/api/v1/products/{pid}/transactions")
        assert history.json()["pagination"]["total"] == 1  # only the seed IN

    def test_single_request_id_dup(self, client):
        """Single tx with duplicate request_id → 409."""
        pid = _create_item(client)
        rid = str(uuid.uuid4())

        res = _post_tx(client, pid, type="IN", qty=10, request_id=rid)
        assert res.status_code == 201

        res = _post_tx(client, pid, type="IN", qty=5, request_id=rid)
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "DUPLICATE_REQUEST_ID"

        # Original tx still intact, duplicate was rejected
        history = client.get(f"/api/v1/products/{pid}/transactions")
        assert history.json()["pagination"]["total"] == 1

    def test_batch_dup_rollback_preserves_stock(self, client):
        """After batch rollback due to dup request_id, stock is unchanged."""
        pid = _create_item(client)
        rid = str(uuid.uuid4())
        _post_tx(client, pid, type="IN", qty=100, request_id=rid)

        # This batch would add 30 to on_hand, but should fail and rollback
        _post_batch(client, pid, [
            {"type": "IN", "qty": 10},
            {"type": "IN", "qty": 20, "request_id": rid},
        ])

        # Verify stock is still 100, not 130
        res = _post_tx(client, pid, type="IN", qty=1)
        assert res.json()["stock"]["on_hand"] == 101  # 100 + 1, not 130 + 1


# ── Tx history filters / pagination ──────────────────────────────

class TestTxHistory:
    def test_filter_by_type(self, client):
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=50)
        _post_tx(client, pid, type="OUT", qty=10)

        res = client.get(f"/api/v1/products/{pid}/transactions?type=IN")
        assert res.json()["pagination"]["total"] == 1
        assert res.json()["data"][0]["type"] == "IN"

    def test_filter_by_bucket(self, client):
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=50)
        _post_tx(client, pid, type="RESERVE", qty=10)

        res = client.get(f"/api/v1/products/{pid}/transactions?bucket=RESERVED")
        assert res.json()["pagination"]["total"] == 1
        assert res.json()["data"][0]["bucket"] == "RESERVED"

    def test_pagination(self, client):
        pid = _create_item(client)
        for _ in range(5):
            _post_tx(client, pid, type="IN", qty=1)

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
        res = _post_tx(client, pid, type="IN", qty=10, reason="入荷")
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
        """Brand-new item with no Tx → stock returns to 0."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=1)
        res = _post_tx(client, pid, type="OUT", qty=1)
        stock = res.json()["stock"]
        assert stock == {"available": 0, "on_hand": 0, "reserved": 0}


# ── Sign-safety tests (符号ミス防止) ─────────────────────────────

class TestSignSafety:
    """Verify that the server always produces the correct qty_delta sign.
    The client never sends a sign — only type + positive qty."""

    def test_in_produces_positive_delta(self, client):
        pid = _create_item(client)
        res = _post_tx(client, pid, type="IN", qty=42)
        assert res.json()["data"]["qty_delta"] == 42

    def test_out_produces_negative_delta(self, client):
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=100)
        res = _post_tx(client, pid, type="OUT", qty=30)
        assert res.json()["data"]["qty_delta"] == -30

    def test_reserve_produces_positive_delta(self, client):
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=100)
        res = _post_tx(client, pid, type="RESERVE", qty=25)
        assert res.json()["data"]["qty_delta"] == 25
        assert res.json()["data"]["bucket"] == "RESERVED"

    def test_unreserve_produces_negative_delta(self, client):
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=100)
        _post_tx(client, pid, type="RESERVE", qty=30)
        res = _post_tx(client, pid, type="UNRESERVE", qty=10)
        assert res.json()["data"]["qty_delta"] == -10
        assert res.json()["data"]["bucket"] == "RESERVED"

    def test_adjust_increase_produces_positive_delta(self, client):
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=10)
        res = _post_tx(client, pid, type="ADJUST", qty=3, direction="INCREASE")
        assert res.json()["data"]["qty_delta"] == 3
        assert res.json()["data"]["bucket"] == "ON_HAND"

    def test_adjust_decrease_produces_negative_delta(self, client):
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=10)
        res = _post_tx(client, pid, type="ADJUST", qty=2, direction="DECREASE")
        assert res.json()["data"]["qty_delta"] == -2
        assert res.json()["data"]["bucket"] == "ON_HAND"

    def test_negative_qty_rejected(self, client):
        """Negative qty is rejected at validation layer."""
        pid = _create_item(client)
        res = _post_tx(client, pid, type="IN", qty=-5)
        assert res.status_code == 400

    def test_batch_sign_correctness(self, client):
        """Batch shipment: OUT produces negative, UNRESERVE produces negative."""
        pid = _create_item(client)
        _post_tx(client, pid, type="IN", qty=100)
        _post_tx(client, pid, type="RESERVE", qty=20)
        res = _post_batch(client, pid, [
            {"type": "OUT", "qty": 20},
            {"type": "UNRESERVE", "qty": 20},
        ])
        assert res.status_code == 201
        data = res.json()["data"]
        # OUT → negative ON_HAND delta
        assert data[0]["qty_delta"] == -20
        assert data[0]["bucket"] == "ON_HAND"
        # UNRESERVE → negative RESERVED delta
        assert data[1]["qty_delta"] == -20
        assert data[1]["bucket"] == "RESERVED"


# ── Invalid combination tests ────────────────────────────────────

class TestInvalidCombinations:
    """Verify that invalid type+direction combinations are rejected."""

    def test_in_with_direction_rejected(self, client):
        pid = _create_item(client)
        res = _post_tx(client, pid, type="IN", qty=10, direction="INCREASE")
        assert res.status_code == 400

    def test_out_with_direction_rejected(self, client):
        pid = _create_item(client)
        res = _post_tx(client, pid, type="OUT", qty=10, direction="DECREASE")
        assert res.status_code == 400

    def test_reserve_with_direction_rejected(self, client):
        pid = _create_item(client)
        res = _post_tx(client, pid, type="RESERVE", qty=10, direction="INCREASE")
        assert res.status_code == 400

    def test_unreserve_with_direction_rejected(self, client):
        pid = _create_item(client)
        res = _post_tx(client, pid, type="UNRESERVE", qty=10, direction="DECREASE")
        assert res.status_code == 400

    def test_adjust_without_direction_rejected(self, client):
        pid = _create_item(client)
        res = _post_tx(client, pid, type="ADJUST", qty=5)
        assert res.status_code == 400

    def test_invalid_type_rejected(self, client):
        pid = _create_item(client)
        res = _post_tx(client, pid, type="MOVE", qty=5)
        assert res.status_code == 400
