"""Item CRUD API tests.

Test IDs (P-*) map to docs/TEST.md §2.
Version values are always taken from response (never hardcoded).
"""

import uuid

from tests.helpers import create_item


class TestCreateItem:
    def test_p1_create_with_all_fields(self, client):
        res = create_item(client)
        assert res.status_code == 201
        data = res.json()["data"]
        assert data["code"] == "PIPE-001"
        assert data["name"] == "ステンレスパイプ 25A"
        assert data["spec"] == "SUS304"
        assert data["unit"] == "本"
        assert data["unit_price"] == 2500
        assert data["unit_weight"] == 3.2
        assert data["reorder_point"] == 10
        assert data["active"] is True
        assert "version" in data
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_without_optional_spec(self, client):
        res = create_item(client, spec=None)
        assert res.status_code == 201
        assert res.json()["data"]["spec"] is None

    def test_p6_missing_required_fields(self, client):
        """必須項目を欠いて作成 → 400."""
        res = client.post("/api/v1/products", json={"code": "X"})
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_p7_duplicate_code(self, client):
        """重複する code で作成 → 400."""
        create_item(client, code="DUP-001")
        res = create_item(client, code="DUP-001")
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_p10_negative_price(self, client):
        """単価に負の値 → 400."""
        res = create_item(client, code="NEG-001", unit_price=-100)
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_negative_weight(self, client):
        res = create_item(client, code="NW-001", unit_weight=-1)
        assert res.status_code == 400

    def test_negative_reorder_point(self, client):
        res = create_item(client, code="NR-001", reorder_point=-5)
        assert res.status_code == 400


class TestListItems:
    def test_p2_list_with_pagination(self, client):
        for i in range(3):
            create_item(client, code=f"ITEM-{i:03d}")

        res = client.get("/api/v1/products?page=1&per_page=2")
        assert res.status_code == 200
        body = res.json()
        assert len(body["data"]) == 2
        assert body["pagination"]["total"] == 3
        assert body["pagination"]["page"] == 1
        assert body["pagination"]["per_page"] == 2

    def test_page2(self, client):
        for i in range(3):
            create_item(client, code=f"ITEM-{i:03d}")

        res = client.get("/api/v1/products?page=2&per_page=2")
        assert res.status_code == 200
        assert len(res.json()["data"]) == 1

    def test_p3_search_by_code(self, client):
        create_item(client, code="PIPE-001", name="パイプA")
        create_item(client, code="VALVE-001", name="バルブA")

        res = client.get("/api/v1/products?q=PIPE")
        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data) == 1
        assert data[0]["code"] == "PIPE-001"

    def test_p3_search_by_name(self, client):
        create_item(client, code="PIPE-001", name="ステンレスパイプ")
        create_item(client, code="VALVE-001", name="ボールバルブ")

        res = client.get("/api/v1/products?q=パイプ")
        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data) == 1
        assert data[0]["name"] == "ステンレスパイプ"

    def test_filter_active_only(self, client):
        create_item(client, code="ACTIVE-001")
        res2 = create_item(client, code="INACTIVE-001")
        item_id = res2.json()["data"]["id"]
        client.delete(f"/api/v1/products/{item_id}")

        res = client.get("/api/v1/products?active=true")
        codes = [d["code"] for d in res.json()["data"]]
        assert "ACTIVE-001" in codes
        assert "INACTIVE-001" not in codes

    def test_filter_inactive_only(self, client):
        create_item(client, code="ACTIVE-001")
        res2 = create_item(client, code="INACTIVE-001")
        item_id = res2.json()["data"]["id"]
        client.delete(f"/api/v1/products/{item_id}")

        res = client.get("/api/v1/products?active=false")
        codes = [d["code"] for d in res.json()["data"]]
        assert "INACTIVE-001" in codes
        assert "ACTIVE-001" not in codes

    def test_empty_list(self, client):
        res = client.get("/api/v1/products")
        assert res.status_code == 200
        assert res.json()["data"] == []
        assert res.json()["pagination"]["total"] == 0


class TestGetItem:
    def test_get_existing(self, client):
        res = create_item(client)
        item_id = res.json()["data"]["id"]

        res = client.get(f"/api/v1/products/{item_id}")
        assert res.status_code == 200
        assert res.json()["data"]["code"] == "PIPE-001"

    def test_p8_not_found(self, client):
        fake_id = uuid.uuid4()
        res = client.get(f"/api/v1/products/{fake_id}")
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "PRODUCT_NOT_FOUND"


class TestUpdateItem:
    """items.version optimistic lock for product updates.

    All version values are read from the create/update response — never hardcoded.
    """

    def test_p4_update_with_correct_version(self, client):
        res = create_item(client)
        data = res.json()["data"]
        item_id = data["id"]
        version = data["version"]

        res = client.patch(
            f"/api/v1/products/{item_id}",
            json={"name": "更新後の名前", "unit_price": 3000, "version": version},
        )
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["name"] == "更新後の名前"
        assert data["unit_price"] == 3000
        assert data["version"] == version + 1
        assert data["code"] == "PIPE-001"

    def test_p9_version_mismatch(self, client):
        res = create_item(client)
        item_id = res.json()["data"]["id"]

        res = client.patch(
            f"/api/v1/products/{item_id}",
            json={"name": "更新", "version": 99},
        )
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "CONFLICT"

    def test_update_not_found(self, client):
        fake_id = uuid.uuid4()
        res = client.patch(
            f"/api/v1/products/{fake_id}",
            json={"name": "x", "version": 1},
        )
        assert res.status_code == 404

    def test_update_duplicate_code(self, client):
        create_item(client, code="A-001")
        res2 = create_item(client, code="B-001")
        data2 = res2.json()["data"]

        res = client.patch(
            f"/api/v1/products/{data2['id']}",
            json={"code": "A-001", "version": data2["version"]},
        )
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_consecutive_updates_increment_version(self, client):
        res = create_item(client)
        data = res.json()["data"]
        item_id = data["id"]
        v = data["version"]

        res = client.patch(
            f"/api/v1/products/{item_id}",
            json={"name": "v2", "version": v},
        )
        v = res.json()["data"]["version"]

        res = client.patch(
            f"/api/v1/products/{item_id}",
            json={"name": "v3", "version": v},
        )
        assert res.status_code == 200
        assert res.json()["data"]["version"] == v + 1


class TestDeleteItem:
    def test_p5_soft_delete(self, client):
        res = create_item(client)
        item_id = res.json()["data"]["id"]

        res = client.delete(f"/api/v1/products/{item_id}")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["id"] == item_id
        assert data["active"] is False

        # 論理削除後も取得可能
        res = client.get(f"/api/v1/products/{item_id}")
        assert res.status_code == 200
        assert res.json()["data"]["active"] is False

    def test_delete_not_found(self, client):
        fake_id = uuid.uuid4()
        res = client.delete(f"/api/v1/products/{fake_id}")
        assert res.status_code == 404
