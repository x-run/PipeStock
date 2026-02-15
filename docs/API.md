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
| INSUFFICIENT_AVAILABLE | 409 | Available 不足で出庫不可 |
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

## 4. Stock エンドポイント

### GET /api/v1/stock

全商品の在庫サマリ一覧を取得する (ダッシュボード用)。

**クエリパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| page | integer | No | ページ番号 |
| per_page | integer | No | 1ページあたりの件数 |
| q | string | No | code または name での部分一致検索 |
| below_reorder | boolean | No | true: 発注点以下の商品のみ |

**レスポンス: 200 OK**

```json
{
  "data": [
    {
      "product": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "code": "PIPE-001",
        "name": "ステンレスパイプ 25A",
        "unit": "本",
        "unit_price": 2500,
        "reorder_point": 10
      },
      "available": 80,
      "on_hand": 100,
      "reserved": 20,
      "total_value": 250000,
      "total_weight": 320.0,
      "below_reorder": false
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 1
  }
}
```
