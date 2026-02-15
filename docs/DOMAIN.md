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
| Reorder Point | 発注点。Available がこの値を下回ったら補充を検討する |
| qty_delta | Tx による在庫の変化量 (正: 増加 / 負: 減少) |

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

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| id | UUID | Yes | 主キー |
| product_id | UUID | Yes | 対象商品 (FK → Product) |
| type | enum | Yes | IN, OUT, ADJUST |
| bucket | enum | Yes | ON_HAND, RESERVED |
| qty_delta | integer | Yes | 変化量 (正 or 負) |
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

| 操作 | type | bucket | qty_delta | 説明 |
|------|------|--------|-----------|------|
| 入庫 | IN | ON_HAND | +N | 商品が倉庫に届いた |
| 出庫 | OUT | ON_HAND | -N | 商品を倉庫から出した |
| 引当 | IN | RESERVED | +N | 注文を受けて在庫を確保 |
| 引当解除 (出荷) | OUT | RESERVED | -N | 出荷完了で Reserved を解放 |
| 棚卸補正 (増) | ADJUST | ON_HAND | +N | 実棚と帳簿の差異を補正 |
| 棚卸補正 (減) | ADJUST | ON_HAND | -N | 実棚と帳簿の差異を補正 |

> **注意**: 引当 → 出荷の一連の流れでは、以下の2つの Tx を同時に作成する:
> 1. `OUT / ON_HAND / -N` (物理在庫から出庫)
> 2. `OUT / RESERVED / -N` (引当を解放)

## 6. 不変条件 (Invariants)

| ID | 不変条件 | 検証タイミング |
|----|---------|---------------|
| INV-1 | On-hand >= 0 | Tx 作成時 |
| INV-2 | Reserved >= 0 | Tx 作成時 |
| INV-3 | Available >= 0 (出庫時) | OUT Tx 作成時 |
| INV-4 | Available = On-hand - Reserved | 常時 (計算で保証) |
| INV-5 | Tx は作成後に変更・削除できない | アプリケーション層で制御 |
| INV-6 | ADJUST は ON_HAND バケットのみに適用可能 | Tx 作成時 |
| INV-7 | qty_delta != 0 | Tx 作成時 |
| INV-8 | 非アクティブ商品に対する Tx は作成不可 | Tx 作成時 |

### INV-3 の詳細: 出庫時の Available チェック

```
出庫リクエスト: OUT / ON_HAND / -N

事前チェック:
  current_available = current_on_hand - current_reserved
  IF current_available < N THEN
    ERROR "Available 不足: 要求={N}, Available={current_available}"
  END IF
```

## 7. ER 図 (テキスト)

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
