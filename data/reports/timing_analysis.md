# Black Friday price timing analysis

Generated: 2026-10-16T09:42:38+09:00
Source snapshot: 2026-10-16T09:36:19+09:00
Source snapshot SHA256: 39173a037cf2520ec4c423fe9687bd4bdbd3cf6e451163212a2ba0ecb815d1a7
Budget: ¥330,200
Target Black Friday: 2026-11-27

## Current actionable candidates

|Rank|Product|Current|Required discount|Feasibility|GPU|Perf|Source|
|---:|---|---:|---:|---|---|---:|---|
|1|G TUNE P6-I7G70BK-B|¥284,700|0.0%|HIGH|rtx 5070|35|direct_structured|
|2|G TUNE FG-A7G70|¥319,800|0.0%|HIGH|rtx 5070|33|direct_structured|
|3|G TUNE DG-I7G70|¥299,800|0.0%|HIGH|rtx 5070|32|direct_structured|
|4|G TUNE FG-A7G6T|¥300,001|0.0%|HIGH|rtx 5060 ti|28|direct_text|
|5|G TUNE DG-A7G70|¥300,001|0.0%|HIGH|rtx 5070|26|direct_text|
|6|G TUNE DG-I5G70|¥279,800|0.0%|HIGH|rtx 5070|22|direct_structured|
|7|G TUNE DG-A5G60|¥194,800|0.0%|HIGH|rtx 5060|15|direct_structured|
|8|Lenovo Legion Pro 5i Gen 10（16型 Intel）|¥337,240|2.1%|HIGH|rtx 5080|40|direct_structured|
|9|G TUNE FG-A7G7T（TGS2026出展記念モデル第2弾）|¥399,800|17.4%|REALISTIC|rtx 5070 ti|38|direct_structured|
|10|G TUNE P5-I7G70BK-C（ブラック）|¥448,800|26.4%|AGGRESSIVE|rtx 5070|32|direct_structured|

## Empirical price-change timing

- Meaningful change sample: **7**
- **観測不足:** 20件未満なので時間帯の傾向は作りません。

## Historical anchors

- 2025-11-19 | Amazon surprise/pre-sale begins | https://game.watch.impress.co.jp/docs/news/2064238.html
- 2025-11-21 | Amazon early sale begins | https://game.watch.impress.co.jp/docs/news/2064238.html
- 2025-11-22 | ROG Strix G16 RTX 5070 Ti 32GB/1TB observed at ¥299,800 ¥299,800 | https://note.com/utopia_pc/n/nf617ebb9eec3
- 2025-11-24 | Amazon main Black Friday begins | https://game.watch.impress.co.jp/docs/news/2064238.html
- 2025-11-24 | TUF Gaming A16 RTX 5070 32GB/1TB observed at ¥219,800 ¥219,800 | https://pc.watch.impress.co.jp/docs/news/todays_sales/2067328.html
- 2025-11-30 | TUF Gaming A16 RTX 5070 32GB/1TB still observed at ¥219,800 ¥219,800 | https://ascii.jp/elem/000/004/356/4356081/
- 2025-11-14 | Lenovo Black Friday campaign begins | https://www.lenovo.com/jp/ja/campaigns/black-friday/

## BF window observation ledger

- Ledger: data/buy_now_observations.jsonl
- Rows loaded: 0
- Rows appended this run: 0
- Only in-stock/low-stock, exact-identity, direct-structured and PIT-valid observations are added.

## Current buy-now decision

- Status: **事前監視継続・公式日程未確認** (PRE_BF_MONITORING)
- Recommendation: 現在価格は事前参考値です。設定期間は各社の公式開催日ではありません。公式ページで2026年の日付範囲を確認できるまではBF価格として扱わず、開催日推定に基づく購入推奨を出しません。
- Full detail: data/reports/buy-now-now.md
- The timing score is a heuristic priority signal, not a probability forecast.

## Rules
- Missing retrieval is not stockout.
- Seller-internal price-change time is never inferred from article publication time.
- Timing observations are empirical only after sufficient sample size.