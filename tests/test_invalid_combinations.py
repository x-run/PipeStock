"""Invalid type+direction combination tests.

Test IDs (IC-*) map to docs/TEST.md §3.4.
"""

from tests.helpers import create_item_id, post_tx


class TestInvalidCombinations:
    """Verify that invalid type+direction combinations are rejected."""

    def test_in_with_direction_rejected(self, client):
        pid = create_item_id(client)
        res = post_tx(client, pid, type="IN", qty=10, direction="INCREASE")
        assert res.status_code == 400

    def test_out_with_direction_rejected(self, client):
        pid = create_item_id(client)
        res = post_tx(client, pid, type="OUT", qty=10, direction="DECREASE")
        assert res.status_code == 400

    def test_reserve_with_direction_rejected(self, client):
        pid = create_item_id(client)
        res = post_tx(client, pid, type="RESERVE", qty=10, direction="INCREASE")
        assert res.status_code == 400

    def test_unreserve_with_direction_rejected(self, client):
        pid = create_item_id(client)
        res = post_tx(client, pid, type="UNRESERVE", qty=10, direction="DECREASE")
        assert res.status_code == 400

    def test_adjust_without_direction_rejected(self, client):
        pid = create_item_id(client)
        res = post_tx(client, pid, type="ADJUST", qty=5)
        assert res.status_code == 400

    def test_invalid_type_rejected(self, client):
        pid = create_item_id(client)
        res = post_tx(client, pid, type="MOVE", qty=5)
        assert res.status_code == 400
