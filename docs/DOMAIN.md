# DOMAIN - ドメインモデル

## 1. 用語定義

| 用語 | 定義 |
|------|------|
| Product | 管理対象の商品マスタ |
| Transaction (Tx) | 在庫変動を記録する不変レコード |
| Bucket | 在庫の区分。ON_HAND または RESERVED |
| On-hand | 倉庫に物理的に存在する在庫数量 |
| Reserved | 注文済み未発送で引き当てられた保留在庫 |
| Available | 出庫可能な在庫数量 (= On-hand - Reserved) |
| Reorder Point | 発注点。Available がこの値以下になったら補充を検討する |
| qty | API 入力の数量 (常に正数, >= 1) |
| qty_delta | DB 上の在庫変化量 (正: 増加 / 負: 減少)。サーバーが type から自動生成 |

## 2. エンティティ

### 2.1 Product

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| id | UUID | Yes | 主キー |
| code | string | Yes | 商品コード (ユニーク) |
| name | string | Yes | 商品名 |
| spec | string | No | 仕様・規格 |
| unit | string | Yes | 単位 (例: 個, 本, kg) |
| unit_price | decimal | Yes | 単価 (JPY) |
| unit_weight | decimal | No | 単位重量 (kg) |
| reorder_point | integer | Yes | 発注点 (デフォルト: 0) |
| active | boolean | Yes | 有効フラグ (デフォルト: true) |
| version | integer | Yes | 楽観ロック用バージョン |
| created_at | timestamp | Yes | 作成日時 |
| updated_at | timestamp | Yes | 更新日時 |

### 2.2 Transaction (Tx)

**API 入力 (TxCreate):**

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| type | enum | Yes | IN, OUT, ADJUST, RESERVE, UNRESERVE |
| qty | integer | Yes | 数量 (>= 1, 常に正数) |
| direction | enum | ADJUST時のみ | INCREASE, DECREASE (ADJUST 以外では指定不可) |
| reason | string | No | 変更理由・備考 |

**DB レコード (inventory_tx):**

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| id | UUID | Yes | 主キー |
| product_id | UUID | Yes | 対象商品 (FK → Product) |
| type | enum | Yes | IN, OUT, ADJUST, RESERVE, UNRESERVE |
| bucket | enum | Yes | ON_HAND, RESERVED (サーバーが type から自動決定) |
| qty_delta | integer | Yes | 変化量 (正 or 負, サーバーが type + direction から自動生成) |
| reason | string | No | 変更理由・備考 |
| created_at | timestamp | Yes | 作成日時 |

## 3. 在庫計算式

```
On-hand   = SUM(qty_delta) WHERE bucket = ON_HAND
Reserved  = SUM(qty_delta) WHERE bucket = RESERVED
Available = On-hand - Reserved
```

在庫テーブルは持たない。常に Tx の集計から算出する。

## 4. 在庫金額・重量の算出

```
在庫金額 = On-hand × unit_price
在庫重量 = On-hand × unit_weight
```

## 5. Tx タイプと想定される操作

### 安全設計: クライアントは正数 qty のみを送り、サーバーが符号と bucket を決定する

| 操作 | API type | API direction | → DB bucket | → DB qty_delta | 説明 |
|------|----------|---------------|-------------|----------------|------|
| 入庫 | IN | — | ON_HAND | +qty | 商品が倉庫に届いた |
| 出庫 | OUT | — | ON_HAND | -qty | 商品を倉庫から出した |
| 引当 | RESERVE | — | RESERVED | +qty | 注文を受けて在庫を確保 |
| 引当解除 | UNRESERVE | — | RESERVED | -qty | 出荷完了で Reserved を解放 |
| 棚卸補正 (増) | ADJUST | INCREASE | ON_HAND | +qty | 実棚と帳簿の差異を補正 |
| 棚卸補正 (減) | ADJUST | DECREASE | ON_HAND | -qty | 実棚と帳簿の差異を補正 |

> **注意**: 引当 → 出荷の一連の流れでは、以下の2つの Tx を batch で同時に作成する:
> 1. `OUT` (qty=N) → DB: ON_HAND / -N (物理在庫から出庫)
> 2. `UNRESERVE` (qty=N) → DB: RESERVED / -N (引当を解放)

### 不正な組み合わせ (400 エラー)

| パターン | 理由 |
|----------|------|
| ADJUST で direction なし | 増減の方向が不明 |
| IN/OUT/RESERVE/UNRESERVE で direction あり | type から符号が一意に決まるため不要 |

## 6. 不変条件 (Invariants)

| ID | 不変条件 | 検証タイミング |
|----|---------|---------------|
| INV-1 | On-hand >= 0 | Tx 作成時 |
| INV-2 | Reserved >= 0 | Tx 作成時 |
| INV-3 | Available >= 0 | Available を減少させる Tx 作成時 (OUT, RESERVE, ADJUST/DECREASE) |
| INV-4 | Available = On-hand - Reserved | 常時 (計算で保証) |
| INV-5 | Tx は作成後に変更・削除できない | アプリケーション層で制御 |
| INV-6 | ADJUST は ON_HAND バケットのみに適用可能 | type マッピングで構造的に保証 |
| INV-7 | qty >= 1 (正数のみ受付) | スキーマバリデーション |
| INV-8 | 非アクティブ商品に対する Tx は作成不可 | Tx 作成時 |

### INV-3 の詳細: Available チェック

Available を減少させる操作は以下の3パターン:

**パターン A: 出庫 (type=OUT, qty=N)**
```
サーバー処理: qty_delta = -N, bucket = ON_HAND
事前チェック:
  current_available = current_on_hand - current_reserved
  IF current_available < N THEN
    ERROR "Available 不足"
  END IF
```

**パターン B: 引当 (type=RESERVE, qty=N)**
```
サーバー処理: qty_delta = +N, bucket = RESERVED
事前チェック:
  current_available = current_on_hand - current_reserved
  IF current_available < N THEN
    ERROR "Available 不足"
  END IF
```

**パターン C: 棚卸補正・減 (type=ADJUST, direction=DECREASE, qty=N)**
```
サーバー処理: qty_delta = -N, bucket = ON_HAND
事前チェック:
  new_available = (current_on_hand - N) - current_reserved
  IF new_available < 0 THEN
    ERROR "Available 不足"
  END IF
```

## 7. 返品検品フロー (QUARANTINE なし方式)

既存の IN / OUT / RESERVE / UNRESERVE を組み合わせて、返品検品の3ステップを表現する。
新しい type や bucket は追加しない。

### 7.1 フロー概要

```
返品到着 ──→ 検品待ち ──→ 検品OK  → 在庫復帰
                       └→ 検品NG  → 廃棄
```

### 7.2 Tx パターン

**ステップ 1: 返品到着 (検品前)** — batch で原子的に2Tx

| # | type | bucket | qty_delta | reason |
|---|------|--------|-----------|--------|
| 1 | IN | ON_HAND | +qty | RETURN_ARRIVED |
| 2 | RESERVE | RESERVED | +qty | RETURN_PENDING |

在庫変動: on_hand +qty / reserved +qty / **available 変化なし**

> 物理在庫は増えるが、検品完了まで reserved でロックするため available は変わらない。

**ステップ 2a: 検品OK (在庫復帰)** — 単一 Tx

| # | type | bucket | qty_delta | reason |
|---|------|--------|-----------|--------|
| 1 | UNRESERVE | RESERVED | -qty | RETURN_OK |

在庫変動: reserved -qty / **available +qty** / on_hand 変化なし

> Reserved のロックを解除し、Available に反映する。

**ステップ 2b: 検品NG (廃棄)** — batch で原子的に2Tx

| # | type | bucket | qty_delta | reason |
|---|------|--------|-----------|--------|
| 1 | UNRESERVE | RESERVED | -qty | RETURN_REJECTED |
| 2 | OUT | ON_HAND | -qty | SCRAP |

在庫変動: reserved -qty / on_hand -qty / **available 変化なし**

> Reserved ロックを解除すると同時に物理在庫を減らすため、Available は変化しない。

### 7.3 reason の定義

| reason | 使用コンテキスト | 説明 |
|--------|-----------------|------|
| RETURN_ARRIVED | 返品到着 (IN) | 返品商品が倉庫に到着 |
| RETURN_PENDING | 返品到着 (RESERVE) | 検品待ちのため Available からロック |
| RETURN_OK | 検品OK (UNRESERVE) | 検品合格、在庫復帰 |
| RETURN_REJECTED | 検品NG (UNRESERVE) | 検品不合格、ロック解除 |
| SCRAP | 検品NG (OUT) | 廃棄による物理在庫の減少 |

> reason はフリーテキストフィールドであり、上記は運用上の規約である。
> バリデーションは行わず、Tx 履歴のフィルタリングや集計に活用する。

### 7.4 Available 計算との整合性

返品フローの全ステップで `Available = On-hand - Reserved` の不変条件 (INV-4) は維持される:

| ステップ | On-hand | Reserved | Available | 変化 |
|---------|---------|----------|-----------|------|
| 返品到着 | +N | +N | ±0 | IN + RESERVE が相殺 |
| 検品OK | ±0 | -N | +N | UNRESERVE で解放 |
| 検品NG | -N | -N | ±0 | OUT + UNRESERVE が相殺 |

## 8. ER 図 (テキスト)

```
+------------------+       +------------------+
|     Product      |       |   Transaction    |
+------------------+       +------------------+
| id          (PK) |<──────| id          (PK) |
| code      (UNQ)  |       | product_id  (FK) |
| name             |       | type             |
| spec             |       | bucket           |
| unit             |       | qty_delta        |
| unit_price       |       | reason           |
| unit_weight      |       | created_at       |
| reorder_point    |       +------------------+
| active           |
| version          |
| created_at       |
| updated_at       |
+------------------+
```
