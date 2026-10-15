# 実店舗価格・在庫の確認と記録

## 対象
実店舗で購入するカテゴリは、メインモニター・マウス・キーボード・スピーカーです。PC自作パーツはオンライン購入のままです。

候補店舗と正式な店舗ページは `config/targets.json` の `purchase_channels.physical_store_candidates` にあります。現在の候補はビックカメラ天神1号館とヨドバシカメラ マルチメディア博多です。

## Web価格を店頭価格として使わない
`data/peripheral_prices.json` にある `current_price_jpy` は監視対象ページのオンライン価格です。店頭対象では比較情報に過ぎず、店頭決済額や支店在庫を証明しません。店頭価格未確認時の予算計算は、目標額またはオンライン参考値を使った保守的な仮計算となり、購入許可は保留されます。

## 店頭確認を入力する項目
`config/targets.json` の対象商品にある以下の項目を、実際に確認した場合だけ記入します。

- `store_price_jpy`: 税込の店頭価格（整数の円）
- `store_price_checked_at`: 確認時刻。例 `2026-11-20T14:35:00+09:00`
- `store_stock_status`: `in_stock` / `low_stock` / `out_of_stock` / `unknown`
- `store_observation_store_id`: `physical_store_candidate_ids` に含まれる店舗ID
- `store_evidence_type`: `in_store_check` / `store_phone_confirmation` / `official_branch_stock_page`
- `store_evidence_notes`: 店員確認などの方法、正確な型番、税込価格と在庫の内容を短く記録
- `store_confirmation_url`: 選択した支店の公式店舗ページと同じホストのHTTPS URL
- `store_model_match`: パッケージ・ページ・店員の確認で完全な型番が一致した場合だけ `true`

オンライン商品ページしか確認していない場合は、これらの店頭証拠項目を埋めないでください。別店舗、類似型番、色違い、取り寄せ表示を店頭在庫ありとみなさないでください。

## 有効期限とゲート
検証処理は、確認時刻、支店ID、証拠種類、メモ、正確な型番照合、店舗公式URLのホストを確認します。現在の運用設定では、通常監視中の有効時間は最大60分、BF監視中は最大30分です。期限超過・未来時刻・必要項目不足・支店不一致は有効価格にしません。

店頭価格と在庫は別の情報です。価格が検証済みでも在庫状態が `unknown` の場合、在庫確認済みとは扱いません。購入前には対象店舗・型番・色・税込レジ価格・在庫を再確認してください。

## データの更新
次回の監視サイクルで `scripts/peripheral_monitor.py` が店頭確認状態を観測スナップショットに反映し、`scripts/intelligence.py` の予算計算が同じ条件で有効性を判定します。自動Web取得は支店への電話や実地確認を代行しないため、未確認は未確認のまま残します。
