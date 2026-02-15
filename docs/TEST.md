# TEST - テスト観点

## 1. テスト方針

- 在庫数量の正確性が最重要。不変条件 (INV-1〜8) を必ずテストする。
- 各 Phase の完了時にテストを実行し、リグレッションがないことを確認する。
- 単体テストとAPIテストを中心に構成し、E2E は Phase 6 で実施する。

---

## 2. 商品マスタ (Phase 2)

### 2.1 正常系

| # | テスト内容 | 期待結果 |
|---|-----------|---------|
| P-1 | 必須項目を全て入力して商品を作成 | 201 Created, 商品が保存される |
| P-2 | 商品一覧を取得 | 200 OK, ページネーション付きで返る |
| P-3 | 商品コード・名前で検索 | 部分一致で該当商品が返る |
| P-4 | 商品を更新 (version 一致) | 200 OK, version がインクリメントされる |
| P-5 | 商品を論理削除 | active が false になる |

### 2.2 異常系

| # | テスト内容 | 期待結果 |
|---|-----------|---------|
| P-6 | 必須項目を欠いて作成 | 400 VALIDATION_ERROR |
| P-7 | 重複する code で作成 | 400 VALIDATION_ERROR |
| P-8 | 存在しない id で取得 | 404 PRODUCT_NOT_FOUND |
| P-9 | version 不一致で更新 | 409 CONFLICT |
| P-10 | 単価に負の値を指定 | 400 VALIDATION_ERROR |

---

## 3. トランザクション・在庫計算 (Phase 3)

### 3.1 正常系

| # | テスト内容 | 期待結果 |
|---|-----------|---------|
| T-1 | type=IN (qty=50) で入庫 | On-hand が増加する |
| T-2 | type=OUT (qty=30) で出庫 (Available 十分) | On-hand が減少する |
| T-3 | type=RESERVE (qty=20) で引当 | Reserved が増加、Available が減少する |
| T-4 | type=UNRESERVE (qty=10) で引当解除 | Reserved が減少、Available が増加する |
| T-5 | type=ADJUST, direction=INCREASE (qty=5) | On-hand が増加する |
| T-6 | type=ADJUST, direction=DECREASE (qty=2) | On-hand が減少する |
| T-7 | 複数 Tx 後の在庫計算が正しい | SUM 集計が合っている |
| T-8 | Tx 履歴を取得 | 新しい順に返る |

### 3.2 異常系 (不変条件)

| # | 不変条件 | テスト内容 | 期待結果 |
|---|---------|-----------|---------|
| T-9 | INV-3 | Available 不足で OUT | 409 INSUFFICIENT_AVAILABLE |
| T-10 | INV-3 | Available ぴったりで OUT | 成功 (境界値) |
| T-11 | INV-3 | Available=0 で OUT (qty=1) | 409 エラー |
| T-12 | INV-6/7 | ADJUST で direction なし | 400 VALIDATION_ERROR |
| T-13 | INV-7 | qty=0 で作成 | 400 VALIDATION_ERROR |
| T-14 | INV-8 | 非アクティブ商品に Tx 作成 | 400 PRODUCT_INACTIVE |
| T-15 | INV-1 | On-hand が負になる ADJUST/DECREASE | 409 エラー |
| T-16 | INV-2 | Reserved が負になる UNRESERVE | 409 エラー |
| T-17 | INV-5 | Tx の更新を試みる | 許可されない (エンドポイント自体がない) |
| T-18 | INV-5 | Tx の削除を試みる | 許可されない (エンドポイント自体がない) |
| T-19 | INV-3 | Available を超える RESERVE | 409 INSUFFICIENT_AVAILABLE |
| T-20 | INV-3 | Available ぴったりの RESERVE | 成功 (境界値) |

### 3.3 符号安全性テスト (Sign Safety)

| # | テスト内容 | 期待結果 |
|---|-----------|---------|
| SS-1 | IN → DB qty_delta が正 | qty_delta == +qty |
| SS-2 | OUT → DB qty_delta が負 | qty_delta == -qty |
| SS-3 | RESERVE → DB qty_delta が正, bucket=RESERVED | qty_delta == +qty |
| SS-4 | UNRESERVE → DB qty_delta が負, bucket=RESERVED | qty_delta == -qty |
| SS-5 | ADJUST/INCREASE → DB qty_delta が正 | qty_delta == +qty |
| SS-6 | ADJUST/DECREASE → DB qty_delta が負 | qty_delta == -qty |
| SS-7 | 負の qty を送信 | 400 エラー |
| SS-8 | batch の符号正確性 | OUT=-N, UNRESERVE=-N |

### 3.4 不正な組み合わせテスト (Invalid Combinations)

| # | テスト内容 | 期待結果 |
|---|-----------|---------|
| IC-1 | IN + direction=INCREASE | 400 エラー |
| IC-2 | OUT + direction=DECREASE | 400 エラー |
| IC-3 | RESERVE + direction=INCREASE | 400 エラー |
| IC-4 | UNRESERVE + direction=DECREASE | 400 エラー |
| IC-5 | ADJUST + direction なし | 400 エラー |
| IC-6 | 不正な type 値 | 400 エラー |

### 3.5 返品検品フローテスト (Return Flow)

| # | テスト内容 | 期待結果 |
|---|-----------|---------|
| R-1 | 返品到着 batch (IN + RESERVE) | on_hand +qty, reserved +qty, available 変化なし |
| R-2 | 検品OK (UNRESERVE) | reserved -qty, available +qty, on_hand 変化なし |
| R-3 | 検品NG batch (UNRESERVE + OUT) | reserved -qty, on_hand -qty, available 変化なし |
| R-4 | 返品到着 → 検品OK のフルフロー | 最終: on_hand +qty, reserved ±0, available +qty |
| R-5 | 返品到着 → 検品NG のフルフロー | 最終: on_hand ±0, reserved ±0, available ±0 |
| R-6 | 検品NG batch で Available 不足 (廃棄の OUT が超過) | 409 エラー, Tx なし |
| R-7 | 返品到着 batch の原子性 (IN は OK だが RESERVE が Available 超過) | 409, Tx なし |

---

## 4. 在庫サマリ (Phase 4)

| # | テスト内容 | 期待結果 |
|---|-----------|---------|
| S-1 | 在庫サマリ一覧取得 | 全商品の On-hand, Reserved, Available が正しい |
| S-2 | 在庫金額 = On-hand × unit_price | 金額が正しく算出される |
| S-3 | 在庫重量 = On-hand × unit_weight | 重量が正しく算出される |
| S-4 | 発注点以下フィルタ | Available <= reorder_point の商品のみ返る |
| S-5 | 商品詳細に stock 情報が含まれる | on_hand, reserved, available が返る |
| S-6 | Tx が0件の商品の在庫サマリ | 全て 0 で返る |

---

## 5. UI (Phase 5)

| # | テスト内容 | 期待結果 |
|---|-----------|---------|
| U-1 | ダッシュボードで Available が太字・メインカラー | 視覚的に主役 |
| U-2 | Reserved が薄い色で表示される | opacity 等で控えめ |
| U-3 | 発注点以下の行が警告色の背景 | 視覚的に警告 |
| U-4 | 数量に単位が表示される | `80 本` のように表示 |
| U-5 | 金額が3桁カンマ区切り | `¥250,000` のように表示 |
| U-6 | 出庫時に Available 不足の警告が表示される | フォーム上で即座に警告 |
| U-7 | 引当解除・出荷で2つの Tx が batch API で同時作成される | 正しく在庫が変動する |

---

## 6. E2E シナリオ (Phase 6)

### シナリオ 1: 基本フロー

```
1. 商品「PIPE-001」を登録
2. 入庫: type=IN, qty=100
   → On-hand=100, Reserved=0, Available=100
3. 引当: type=RESERVE, qty=30
   → On-hand=100, Reserved=30, Available=70
4. 出荷 (batch): type=OUT qty=30 + type=UNRESERVE qty=30
   → On-hand=70, Reserved=0, Available=70
5. 在庫サマリで確認
   → 金額・重量が正しく算出されている
```

### シナリオ 2: Available 不足

```
1. 商品「PIPE-002」を登録
2. 入庫: type=IN, qty=10
3. 引当: type=RESERVE, qty=8
   → Available=2
4. 出庫: type=OUT, qty=5
   → エラー: Available 不足 (要求=5, Available=2)
5. 出庫: type=OUT, qty=2
   → 成功: Available=0
```

### シナリオ 3: 棚卸補正

```
1. 商品「PIPE-003」を登録
2. 入庫: type=IN, qty=50
3. 棚卸で実数が 48 と判明
4. 補正: type=ADJUST, direction=DECREASE, qty=2
   → On-hand=48, Available=48
```

### シナリオ 4: 引当超過

```
1. 商品「PIPE-004」を登録
2. 入庫: type=IN, qty=10
   → Available=10
3. 引当: type=RESERVE, qty=10
   → Available=0
4. 引当: type=RESERVE, qty=1
   → エラー: Available 不足 (引当要求=1, Available=0)
```

### シナリオ 5: 返品検品フロー

```
1. 商品「PIPE-005」を登録
2. 入庫: type=IN, qty=100
   → On-hand=100, Reserved=0, Available=100
3. 返品到着 (batch): IN qty=10 + RESERVE qty=10
   → On-hand=110, Reserved=10, Available=100
4. 検品OK: UNRESERVE qty=7
   → On-hand=110, Reserved=3, Available=107
5. 検品NG (batch): UNRESERVE qty=3 + OUT qty=3
   → On-hand=107, Reserved=0, Available=107
```

### シナリオ 6: 非アクティブ商品

```
1. 商品「PIPE-005」を登録
2. 入庫: type=IN, qty=10
3. 商品を論理削除 (active=false)
4. 入庫: type=IN, qty=5
   → エラー: PRODUCT_INACTIVE
```
