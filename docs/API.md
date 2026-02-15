# API - REST API 仕様

## 1. 共通仕様

- ベース URL: `/api/v1`
- レスポンス形式: JSON
- 日時形式: ISO 8601 (`2026-01-15T09:30:00Z`)
- ページネーション: `?page=1&per_page=20` (デフォルト: per_page=20, 最大: 100)
- エラーレスポンス形式:

```json
{
  "error": {
    "code": "INSUFFICIENT_AVAILABLE",
    "message": "Available 不足: 要求=10, Available=5"
  }
}
```

### エラーコード一覧

| コード | HTTP Status | 説明 |
|--------|-------------|------|
| VALIDATION_ERROR | 400 | 入力値バリデーションエラー |
| PRODUCT_NOT_FOUND | 404 | 商品が見つからない |
| PRODUCT_INACTIVE | 400 | 非アクティブ商品への操作 |
| INSUFFICIENT_ON_HAND | 409 | On-hand 不足 (INV-1) |
| INSUFFICIENT_RESERVED | 409 | Reserved 不足 (INV-2) |
| INSUFFICIENT_AVAILABLE | 409 | Available 不足 (INV-3) |
| DUPLICATE_REQUEST_ID | 409 | request_id 重複 |
| CONFLICT | 409 | 楽観ロック競合 |

---

## 2. Product エンドポイント

### GET /api/v1/products

商品一覧を取得する。

**クエリパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| page | integer | No | ページ番号 (デフォルト: 1) |
| per_page | integer | No | 1ページあたりの件数 (デフォルト: 20) |
| active | boolean | No | true: アクティブのみ / false: 非アクティブのみ |
| q | string | No | code または name での部分一致検索 |

**レスポンス: 200 OK**

```json
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "code": "PIPE-001",
      "name": "ステンレスパイプ 25A",
      "spec": "SUS304 / 外径34mm / 肉厚1.5mm",
      "unit": "本",
      "unit_price": 2500,
      "unit_weight": 3.2,
      "reorder_point": 10,
      "active": true,
      "version": 1,
      "created_at": "2026-01-15T09:00:00Z",
      "updated_at": "2026-01-15T09:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 1
  }
}
```

---

### POST /api/v1/products

商品を新規作成する。

**リクエストボディ:**

```json
{
  "code": "PIPE-001",
  "name": "ステンレスパイプ 25A",
  "spec": "SUS304 / 外径34mm / 肉厚1.5mm",
  "unit": "本",
  "unit_price": 2500,
  "unit_weight": 3.2,
  "reorder_point": 10
}
```

| フィールド | 型 | 必須 | バリデーション |
|-----------|-----|------|---------------|
| code | string | Yes | 1〜50文字, ユニーク |
| name | string | Yes | 1〜200文字 |
| spec | string | No | 最大500文字 |
| unit | string | Yes | 1〜20文字 |
| unit_price | decimal | Yes | >= 0 |
| unit_weight | decimal | No | >= 0 |
| reorder_point | integer | Yes | >= 0 |

**レスポンス: 201 Created**

```json
{
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "code": "PIPE-001",
    "name": "ステンレスパイプ 25A",
    "spec": "SUS304 / 外径34mm / 肉厚1.5mm",
    "unit": "本",
    "unit_price": 2500,
    "unit_weight": 3.2,
    "reorder_point": 10,
    "active": true,
    "version": 1,
    "created_at": "2026-01-15T09:00:00Z",
    "updated_at": "2026-01-15T09:00:00Z"
  }
}
```

---

### GET /api/v1/products/:id

商品の詳細を取得する。在庫サマリを含む。

**レスポンス: 200 OK**

```json
{
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "code": "PIPE-001",
    "name": "ステンレスパイプ 25A",
    "spec": "SUS304 / 外径34mm / 肉厚1.5mm",
    "unit": "本",
    "unit_price": 2500,
    "unit_weight": 3.2,
    "reorder_point": 10,
    "active": true,
    "version": 1,
    "created_at": "2026-01-15T09:00:00Z",
    "updated_at": "2026-01-15T09:00:00Z",
    "stock": {
      "available": 80,
      "on_hand": 100,
      "reserved": 20,
      "total_value": 250000,
      "total_weight": 320.0
    }
  }
}
```

---

### PATCH /api/v1/products/:id

商品を更新する。楽観ロックのため `version` を必須とする。

**リクエストボディ:**

```json
{
  "name": "ステンレスパイプ 25A (改)",
  "unit_price": 2800,
  "version": 1
}
```

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| version | integer | Yes | 現在のバージョン (楽観ロック) |
| その他 | - | No | 更新したいフィールドのみ送信 |

**レスポンス: 200 OK** - 更新後の Product を返す

**エラー: 409 Conflict** - version が一致しない場合

---

### DELETE /api/v1/products/:id

商品を論理削除する (active = false)。

**レスポンス: 200 OK**

```json
{
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "active": false
  }
}
```

---

## 3. Transaction エンドポイント

### GET /api/v1/products/:product_id/transactions

指定商品の Tx 履歴を取得する。

**クエリパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| page | integer | No | ページ番号 |
| per_page | integer | No | 1ページあたりの件数 |
| type | string | No | IN / OUT / ADJUST / RESERVE / UNRESERVE でフィルタ |
| bucket | string | No | ON_HAND / RESERVED でフィルタ |

**レスポンス: 200 OK**

```json
{
  "data": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "product_id": "550e8400-e29b-41d4-a716-446655440000",
      "type": "IN",
      "bucket": "ON_HAND",
      "qty_delta": 50,
      "reason": "仕入先A社より入荷",
      "created_at": "2026-01-15T10:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 1
  }
}
```

---

### POST /api/v1/products/:product_id/transactions

Tx を新規作成する。在庫が変動する。

**安全設計**: クライアントは正数 `qty` のみを送信し、`type` によってサーバーが符号 (`qty_delta`) と `bucket` を自動決定する。

**リクエストボディ:**

```json
{
  "type": "IN",
  "qty": 50,
  "reason": "仕入先A社より入荷"
}
```

| フィールド | 型 | 必須 | バリデーション |
|-----------|-----|------|---------------|
| type | enum | Yes | IN, OUT, ADJUST, RESERVE, UNRESERVE |
| qty | integer | Yes | >= 1 (正数のみ) |
| direction | enum | ADJUST時のみ | INCREASE, DECREASE |
| reason | string | No | 最大500文字 |

**type → DB マッピング:**

| type | direction | → bucket | → qty_delta |
|------|-----------|----------|-------------|
| IN | — | ON_HAND | +qty |
| OUT | — | ON_HAND | -qty |
| RESERVE | — | RESERVED | +qty |
| UNRESERVE | — | RESERVED | -qty |
| ADJUST | INCREASE | ON_HAND | +qty |
| ADJUST | DECREASE | ON_HAND | -qty |

**ビジネスルール:**

- ADJUST には `direction` が必須 (なければ 400)
- IN/OUT/RESERVE/UNRESERVE に `direction` を指定すると 400
- type=OUT → Available チェック: `Available >= qty` でなければ 409
- type=RESERVE → Available チェック: `Available >= qty` でなければ 409
- type=ADJUST, direction=DECREASE → Available チェック: `new_available >= 0` でなければ 409
- 対象商品が active=false の場合、400 エラー

**レスポンス: 201 Created**

```json
{
  "data": {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "product_id": "550e8400-e29b-41d4-a716-446655440000",
    "type": "IN",
    "bucket": "ON_HAND",
    "qty_delta": 50,
    "reason": "仕入先A社より入荷",
    "created_at": "2026-01-15T10:00:00Z"
  },
  "stock": {
    "available": 80,
    "on_hand": 100,
    "reserved": 20
  }
}
```

---

### POST /api/v1/products/:product_id/transactions/batch

複数の Tx を原子的に作成する。引当解除・出荷のような複合操作で使用する。
全 Tx が成功するか、全て失敗する (all-or-nothing)。

**リクエストボディ:**

```json
{
  "transactions": [
    {
      "type": "OUT",
      "qty": 30,
      "reason": "出荷 注文#1234"
    },
    {
      "type": "UNRESERVE",
      "qty": 30,
      "reason": "出荷 注文#1234"
    }
  ]
}
```

| フィールド | 型 | 必須 | バリデーション |
|-----------|-----|------|---------------|
| transactions | array | Yes | 1〜10件 |
| transactions[].type | enum | Yes | IN, OUT, ADJUST, RESERVE, UNRESERVE |
| transactions[].qty | integer | Yes | >= 1 |
| transactions[].direction | enum | ADJUST時のみ | INCREASE, DECREASE |
| transactions[].reason | string | No | 最大500文字 |

**ビジネスルール:**

- 全 Tx に対して個別 Tx と同じバリデーション (type/direction の組み合わせチェック含む) を適用
- 全 Tx の結果を合算した上で不変条件を検証する (中間状態では判定しない)

#### 利用例: 引当解除・出荷

→ 下記「レスポンス: 201 Created」を参照

#### 利用例: 返品到着 (検品前)

物理在庫を増やしつつ、検品完了まで Reserved でロックする。

```json
{
  "transactions": [
    {
      "type": "IN",
      "qty": 5,
      "reason": "RETURN_ARRIVED"
    },
    {
      "type": "RESERVE",
      "qty": 5,
      "reason": "RETURN_PENDING"
    }
  ]
}
```

レスポンス例 (初期在庫: on_hand=100, reserved=0):

```json
{
  "data": [
    { "type": "IN", "bucket": "ON_HAND", "qty_delta": 5, "reason": "RETURN_ARRIVED", "..." : "..." },
    { "type": "RESERVE", "bucket": "RESERVED", "qty_delta": 5, "reason": "RETURN_PENDING", "..." : "..." }
  ],
  "stock": { "available": 100, "on_hand": 105, "reserved": 5 }
}
```

> available は変化しない (IN +5 と RESERVE +5 が相殺)。

#### 利用例: 検品NG (廃棄)

Reserved ロックを解除すると同時に物理在庫を減らす。

```json
{
  "transactions": [
    {
      "type": "UNRESERVE",
      "qty": 5,
      "reason": "RETURN_REJECTED"
    },
    {
      "type": "OUT",
      "qty": 5,
      "reason": "SCRAP"
    }
  ]
}
```

レスポンス例 (在庫: on_hand=105, reserved=5, available=100):

```json
{
  "data": [
    { "type": "UNRESERVE", "bucket": "RESERVED", "qty_delta": -5, "reason": "RETURN_REJECTED", "..." : "..." },
    { "type": "OUT", "bucket": "ON_HAND", "qty_delta": -5, "reason": "SCRAP", "..." : "..." }
  ],
  "stock": { "available": 100, "on_hand": 100, "reserved": 0 }
}
```

> available は変化しない (UNRESERVE -5 と OUT -5 が相殺)。

**レスポンス: 201 Created**

```json
{
  "data": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "product_id": "550e8400-e29b-41d4-a716-446655440000",
      "type": "OUT",
      "bucket": "ON_HAND",
      "qty_delta": -30,
      "reason": "出荷 注文#1234",
      "created_at": "2026-01-15T14:00:00Z"
    },
    {
      "id": "660e8400-e29b-41d4-a716-446655440002",
      "product_id": "550e8400-e29b-41d4-a716-446655440000",
      "type": "UNRESERVE",
      "bucket": "RESERVED",
      "qty_delta": -30,
      "reason": "出荷 注文#1234",
      "created_at": "2026-01-15T14:00:00Z"
    }
  ],
  "stock": {
    "available": 80,
    "on_hand": 70,
    "reserved": 0
  }
}
```

---

## 4. Dashboard エンドポイント

### GET /api/v1/dashboard/stock/top

ダッシュボード棒グラフ用。在庫上位 N 商品と「その他」合計を返す。

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|-----------|-----|------|----------|------|
| metric | string | No | qty | `qty`: on_hand 降順 / `value`: stock_value 降順 |
| limit | integer | No | 10 | 上位 N 件 (1〜20) |
| include_inactive | boolean | No | false | true: 非アクティブ商品も含む |

**レスポンス: 200 OK**

```json
{
  "data": [
    {
      "product_id": "550e8400-e29b-41d4-a716-446655440000",
      "code": "PIPE-001",
      "name": "ステンレスパイプ 25A",
      "unit": "本",
      "unit_price": 2500,
      "on_hand": 120,
      "reserved_total": 30,
      "reserved_pending_return": 10,
      "reserved_pending_order": 5,
      "available": 90,
      "stock_value": 300000
    }
  ],
  "others_total": {
    "on_hand": 50,
    "reserved_total": 5,
    "reserved_pending_return": 0,
    "reserved_pending_order": 0,
    "available": 45,
    "stock_value": 125000
  }
}
```

**フィールド説明:**

| フィールド | 説明 |
|-----------|------|
| reserved_total | bucket=RESERVED の qty_delta SUM |
| reserved_pending_return | reserved_total のうち reason="RETURN_PENDING" の分 |
| reserved_pending_order | reserved_total のうち reason="ORDER_PENDING_SHIPMENT" の分 (将来用, 現在は 0) |
| stock_value | on_hand × unit_price |
| others_total | TopN に含まれない商品の合計値 |

---

## 5. Stock 一覧エンドポイント

### GET /api/v1/stock

在庫一覧を取得する (検索・ソート・ページング)。ダッシュボードの「もっと見る」先。

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|-----------|-----|------|----------|------|
| q | string | No | — | code / name / spec 部分一致検索 |
| sort | string | No | qty_desc | `qty_desc` / `qty_asc` / `value_desc` / `value_asc` / `updated_desc` |
| page | integer | No | 1 | ページ番号 |
| per_page | integer | No | 20 | 1ページあたりの件数 (最大 100) |
| include_inactive | boolean | No | false | true: 非アクティブ商品も含む |

**レスポンス: 200 OK**

```json
{
  "data": [
    {
      "product_id": "550e8400-e29b-41d4-a716-446655440000",
      "code": "PIPE-001",
      "name": "ステンレスパイプ 25A",
      "spec": "SUS304 / 外径34mm",
      "unit": "本",
      "unit_price": 2500,
      "unit_weight": 3.2,
      "reorder_point": 10,
      "on_hand": 120,
      "reserved_total": 30,
      "reserved_pending_return": 10,
      "reserved_pending_order": 0,
      "available": 90,
      "stock_value": 300000,
      "needs_reorder": false
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 1
  }
}
```

**フィールド説明:**

| フィールド | 説明 |
|-----------|------|
| needs_reorder | `available <= reorder_point` の場合 true |
| その他 | Dashboard Top と同じ指標定義 |
