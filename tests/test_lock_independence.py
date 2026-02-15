"""Lock independence tests.

Verify that items.version (product update lock) and stock_heads.version
(inventory tx lock) operate independently — neither interferes with the other.
"""

import uuid as uuid_mod

from app.models import StockHead

from tests.helpers import create_item, post_tx


class TestLockIndependence:
    def test_item_update_does_not_affect_stock_head_version(
        self, client, db_session
    ):
        """PATCH /products/:id bumps items.version but NOT stock_heads.version."""
        res = create_item(client)
        data = res.json()["data"]
        item_id = data["id"]
        item_uuid = uuid_mod.UUID(item_id)
        item_version = data["version"]

        # Read initial stock_head version
        db_session.expire_all()
        sh = db_session.query(StockHead).filter(
            StockHead.item_id == item_uuid
        ).first()
        sh_version_before = sh.version

        # Update item (bumps items.version)
        res = client.patch(
            f"/api/v1/products/{item_id}",
            json={"name": "updated name", "version": item_version},
        )
        assert res.status_code == 200
        assert res.json()["data"]["version"] == item_version + 1

        # stock_heads.version must be unchanged
        db_session.expire_all()
        sh = db_session.query(StockHead).filter(
            StockHead.item_id == item_uuid
        ).first()
        assert sh.version == sh_version_before

    def test_tx_creation_does_not_affect_item_version(self, client):
        """POST /products/:id/transactions bumps stock_heads.version
        but NOT items.version."""
        res = create_item(client)
        data = res.json()["data"]
        item_id = data["id"]
        item_version_before = data["version"]

        # Create several transactions (bumps stock_heads.version)
        post_tx(client, item_id, type="IN", qty=50)
        post_tx(client, item_id, type="OUT", qty=10)
        post_tx(client, item_id, type="RESERVE", qty=5)

        # items.version must be unchanged
        res = client.get(f"/api/v1/products/{item_id}")
        assert res.json()["data"]["version"] == item_version_before

    def test_both_locks_work_after_mixed_operations(self, client, db_session):
        """After interleaved item updates and tx creations, both locks
        still work correctly."""
        res = create_item(client)
        data = res.json()["data"]
        item_id = data["id"]
        item_uuid = uuid_mod.UUID(item_id)
        v = data["version"]

        # Tx → items.version unchanged
        post_tx(client, item_id, type="IN", qty=100)

        # Item update → stock_heads.version unchanged
        res = client.patch(
            f"/api/v1/products/{item_id}",
            json={"name": "v2", "version": v},
        )
        v = res.json()["data"]["version"]

        # Another tx
        post_tx(client, item_id, type="OUT", qty=20)

        # Another item update (using current version)
        res = client.patch(
            f"/api/v1/products/{item_id}",
            json={"name": "v3", "version": v},
        )
        assert res.status_code == 200
        v = res.json()["data"]["version"]

        # Verify final state
        db_session.expire_all()
        sh = db_session.query(StockHead).filter(
            StockHead.item_id == item_uuid
        ).first()
        assert sh.version == 2  # 2 tx calls

        res = client.get(f"/api/v1/products/{item_id}")
        assert res.json()["data"]["version"] == v  # 2 patches from initial
