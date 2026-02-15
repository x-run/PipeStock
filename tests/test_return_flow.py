"""Return inspection flow tests (QUARANTINE なし方式).

Test IDs (R-*) map to docs/TEST.md §3.5.

Patterns:
  - Return arrival: batch IN + RESERVE  (on_hand +N, reserved +N, available ±0)
  - Inspection OK:  UNRESERVE            (reserved -N, available +N)
  - Inspection NG:  batch UNRESERVE + OUT (reserved -N, on_hand -N, available ±0)
"""

import uuid

from tests.helpers import create_item_id, post_batch, post_tx


class TestReturnFlow:
    # ── R-1: Return arrival ──────────────────────────────────

    def test_r1_return_arrival_batch(self, client):
        """Return arrival: IN + RESERVE atomically.
        on_hand increases, reserved increases, available unchanged."""
        pid = create_item_id(client)
        post_tx(client, pid, type="IN", qty=100)

        res = post_batch(client, pid, [
            {"type": "IN", "qty": 10, "reason": "RETURN_ARRIVED"},
            {"type": "RESERVE", "qty": 10, "reason": "RETURN_PENDING"},
        ])
        assert res.status_code == 201
        stock = res.json()["stock"]
        assert stock["on_hand"] == 110
        assert stock["reserved"] == 10
        assert stock["available"] == 100  # unchanged

    # ── R-2: Inspection OK ───────────────────────────────────

    def test_r2_inspection_ok(self, client):
        """Inspection OK: UNRESERVE releases reserved, available increases."""
        pid = create_item_id(client)
        post_tx(client, pid, type="IN", qty=100)
        post_batch(client, pid, [
            {"type": "IN", "qty": 10, "reason": "RETURN_ARRIVED"},
            {"type": "RESERVE", "qty": 10, "reason": "RETURN_PENDING"},
        ])

        res = post_tx(client, pid, type="UNRESERVE", qty=10, reason="RETURN_OK")
        assert res.status_code == 201
        stock = res.json()["stock"]
        assert stock["on_hand"] == 110  # unchanged from arrival
        assert stock["reserved"] == 0
        assert stock["available"] == 110  # +10 from before arrival

    # ── R-3: Inspection NG (scrap) ───────────────────────────

    def test_r3_inspection_ng_scrap(self, client):
        """Inspection NG: UNRESERVE + OUT atomically.
        reserved decreases, on_hand decreases, available unchanged."""
        pid = create_item_id(client)
        post_tx(client, pid, type="IN", qty=100)
        post_batch(client, pid, [
            {"type": "IN", "qty": 10, "reason": "RETURN_ARRIVED"},
            {"type": "RESERVE", "qty": 10, "reason": "RETURN_PENDING"},
        ])

        res = post_batch(client, pid, [
            {"type": "UNRESERVE", "qty": 10, "reason": "RETURN_REJECTED"},
            {"type": "OUT", "qty": 10, "reason": "SCRAP"},
        ])
        assert res.status_code == 201
        stock = res.json()["stock"]
        assert stock["on_hand"] == 100   # back to original
        assert stock["reserved"] == 0
        assert stock["available"] == 100  # unchanged from before arrival

    # ── R-4: Full flow — arrival → OK ────────────────────────

    def test_r4_full_flow_arrival_then_ok(self, client):
        """Full return flow: arrival → inspection OK.
        Net effect: available +N."""
        pid = create_item_id(client)
        post_tx(client, pid, type="IN", qty=100)

        post_batch(client, pid, [
            {"type": "IN", "qty": 10, "reason": "RETURN_ARRIVED"},
            {"type": "RESERVE", "qty": 10, "reason": "RETURN_PENDING"},
        ])

        res = post_tx(client, pid, type="UNRESERVE", qty=10, reason="RETURN_OK")
        stock = res.json()["stock"]
        assert stock["on_hand"] == 110
        assert stock["reserved"] == 0
        assert stock["available"] == 110  # net: +10

    # ── R-5: Full flow — arrival → NG ────────────────────────

    def test_r5_full_flow_arrival_then_ng(self, client):
        """Full return flow: arrival → inspection NG (scrap).
        Net effect: zero change to all stock levels."""
        pid = create_item_id(client)
        post_tx(client, pid, type="IN", qty=100)

        post_batch(client, pid, [
            {"type": "IN", "qty": 10, "reason": "RETURN_ARRIVED"},
            {"type": "RESERVE", "qty": 10, "reason": "RETURN_PENDING"},
        ])

        res = post_batch(client, pid, [
            {"type": "UNRESERVE", "qty": 10, "reason": "RETURN_REJECTED"},
            {"type": "OUT", "qty": 10, "reason": "SCRAP"},
        ])
        stock = res.json()["stock"]
        assert stock["on_hand"] == 100
        assert stock["reserved"] == 0
        assert stock["available"] == 100  # net: ±0

    # ── R-6: Scrap batch fails if qty exceeds reserved ───────

    def test_r6_scrap_exceeds_reserved(self, client):
        """Scrap UNRESERVE qty > reserved → 409, no Tx persisted."""
        pid = create_item_id(client)
        post_tx(client, pid, type="IN", qty=50)
        post_batch(client, pid, [
            {"type": "IN", "qty": 5, "reason": "RETURN_ARRIVED"},
            {"type": "RESERVE", "qty": 5, "reason": "RETURN_PENDING"},
        ])
        # State: on_hand=55, reserved=5, available=50

        # Try to scrap 20 (more than reserved=5)
        res = post_batch(client, pid, [
            {"type": "UNRESERVE", "qty": 20, "reason": "RETURN_REJECTED"},
            {"type": "OUT", "qty": 20, "reason": "SCRAP"},
        ])
        assert res.status_code == 409

        # Verify nothing persisted from the failed batch
        history = client.get(f"/api/v1/products/{pid}/transactions")
        # 1 (initial IN) + 2 (return arrival batch) = 3
        assert history.json()["pagination"]["total"] == 3

    # ── R-7: Return arrival batch atomicity ──────────────────

    def test_r7_arrival_batch_atomicity(self, client):
        """Return arrival batch with duplicate request_id → 409.
        Neither IN nor RESERVE is persisted (all-or-nothing)."""
        pid = create_item_id(client)
        rid = str(uuid.uuid4())
        post_tx(client, pid, type="IN", qty=50, request_id=rid)

        res = post_batch(client, pid, [
            {"type": "IN", "qty": 5, "reason": "RETURN_ARRIVED"},
            {"type": "RESERVE", "qty": 5, "reason": "RETURN_PENDING",
             "request_id": rid},  # duplicate!
        ])
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "DUPLICATE_REQUEST_ID"

        # Neither tx persisted
        history = client.get(f"/api/v1/products/{pid}/transactions")
        assert history.json()["pagination"]["total"] == 1  # only the seed IN

    # ── Partial OK + partial NG ──────────────────────────────

    def test_partial_ok_and_partial_ng(self, client):
        """Return 10 items, 7 pass inspection, 3 fail → final available +7."""
        pid = create_item_id(client)
        post_tx(client, pid, type="IN", qty=100)

        # Return arrival: 10 units
        post_batch(client, pid, [
            {"type": "IN", "qty": 10, "reason": "RETURN_ARRIVED"},
            {"type": "RESERVE", "qty": 10, "reason": "RETURN_PENDING"},
        ])

        # Inspection OK for 7
        post_tx(client, pid, type="UNRESERVE", qty=7, reason="RETURN_OK")

        # Inspection NG for 3
        res = post_batch(client, pid, [
            {"type": "UNRESERVE", "qty": 3, "reason": "RETURN_REJECTED"},
            {"type": "OUT", "qty": 3, "reason": "SCRAP"},
        ])
        assert res.status_code == 201
        stock = res.json()["stock"]
        assert stock["on_hand"] == 107
        assert stock["reserved"] == 0
        assert stock["available"] == 107  # net: +7 (only OK items)
