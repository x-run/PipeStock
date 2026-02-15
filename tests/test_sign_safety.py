"""Sign-safety tests (符号ミス防止).

Test IDs (SS-*) map to docs/TEST.md §3.3.
Verify that the server always produces the correct qty_delta sign.
The client never sends a sign — only type + positive qty.
"""

from tests.helpers import create_item_id, post_batch, post_tx


class TestSignSafety:
    def test_in_produces_positive_delta(self, client):
        pid = create_item_id(client)
        res = post_tx(client, pid, type="IN", qty=42)
        assert res.json()["data"]["qty_delta"] == 42

    def test_out_produces_negative_delta(self, client):
        pid = create_item_id(client)
        post_tx(client, pid, type="IN", qty=100)
        res = post_tx(client, pid, type="OUT", qty=30)
        assert res.json()["data"]["qty_delta"] == -30

    def test_reserve_produces_positive_delta(self, client):
        pid = create_item_id(client)
        post_tx(client, pid, type="IN", qty=100)
        res = post_tx(client, pid, type="RESERVE", qty=25)
        assert res.json()["data"]["qty_delta"] == 25
        assert res.json()["data"]["bucket"] == "RESERVED"

    def test_unreserve_produces_negative_delta(self, client):
        pid = create_item_id(client)
        post_tx(client, pid, type="IN", qty=100)
        post_tx(client, pid, type="RESERVE", qty=30)
        res = post_tx(client, pid, type="UNRESERVE", qty=10)
        assert res.json()["data"]["qty_delta"] == -10
        assert res.json()["data"]["bucket"] == "RESERVED"

    def test_adjust_increase_produces_positive_delta(self, client):
        pid = create_item_id(client)
        post_tx(client, pid, type="IN", qty=10)
        res = post_tx(client, pid, type="ADJUST", qty=3, direction="INCREASE")
        assert res.json()["data"]["qty_delta"] == 3
        assert res.json()["data"]["bucket"] == "ON_HAND"

    def test_adjust_decrease_produces_negative_delta(self, client):
        pid = create_item_id(client)
        post_tx(client, pid, type="IN", qty=10)
        res = post_tx(client, pid, type="ADJUST", qty=2, direction="DECREASE")
        assert res.json()["data"]["qty_delta"] == -2
        assert res.json()["data"]["bucket"] == "ON_HAND"

    def test_negative_qty_rejected(self, client):
        """Negative qty is rejected at validation layer."""
        pid = create_item_id(client)
        res = post_tx(client, pid, type="IN", qty=-5)
        assert res.status_code == 400

    def test_batch_sign_correctness(self, client):
        """Batch shipment: OUT produces negative, UNRESERVE produces negative."""
        pid = create_item_id(client)
        post_tx(client, pid, type="IN", qty=100)
        post_tx(client, pid, type="RESERVE", qty=20)
        res = post_batch(client, pid, [
            {"type": "OUT", "qty": 20},
            {"type": "UNRESERVE", "qty": 20},
        ])
        assert res.status_code == 201
        data = res.json()["data"]
        assert data[0]["qty_delta"] == -20
        assert data[0]["bucket"] == "ON_HAND"
        assert data[1]["qty_delta"] == -20
        assert data[1]["bucket"] == "RESERVED"
