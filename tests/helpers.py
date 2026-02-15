"""Shared test helpers for creating items and posting transactions."""


def create_item(client, **overrides):
    """Create an item via API and return the full response."""
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
    return client.post("/api/v1/products", json=payload)


def create_item_id(client, **overrides) -> str:
    """Create an item via API and return its id."""
    res = create_item(client, **overrides)
    assert res.status_code == 201
    return res.json()["data"]["id"]


def post_tx(client, item_id, **kw):
    """POST a single transaction."""
    payload = {"type": "IN", "qty": 1}
    payload.update(kw)
    return client.post(f"/api/v1/products/{item_id}/transactions", json=payload)


def post_batch(client, item_id, txs):
    """POST a batch of transactions."""
    return client.post(
        f"/api/v1/products/{item_id}/transactions/batch",
        json={"transactions": txs},
    )


def post_sale(client, **kw):
    """POST a single sales event."""
    payload = {"type": "SALE", "amount_yen": 1000}
    payload.update(kw)
    return client.post("/api/v1/sales", json=payload)
