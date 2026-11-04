# Black Friday price timing analysis

Generated: 2026-11-04T18:31:13+09:00
Source snapshot: 2026-11-04T18:25:04+09:00
Source snapshot SHA256: 5b5d71e52887c479b9d28b1566e019cd023ba9b23e1fff137f27fad5ca5d6a7e
Budget: ¥360,000
U.S. Black Friday calendar reference only (not official retailer sale dates): 2026-11-27

## Completed-PC / BTO benchmark references (not DIY purchase candidates)

The primary purchase method is self-build. These completed-PC listings are price/performance benchmarks only; they do not authorize a purchase and must not be used as component prices or as the DIY build's checkout total.

|Rank|Completed-PC reference model|Current reference price|Required drop to target|Reference feasibility|GPU|Perf|Source|
|---:|---|---:|---:|---|---|---:|---|
|1|G TUNE P6-I7G70BK-B|¥284,700|0.0%|HIGH|rtx 5070|35|direct_structured|
|2|G TUNE DG-I7G70|¥299,800|0.0%|HIGH|rtx 5070|32|direct_structured|
|3|G TUNE DG-I5G70|¥279,800|0.0%|HIGH|rtx 5070|22|direct_structured|
|4|THIRDWAVE AD-R7A56C-0AW (Ryzen 7 7700 / RTX 5060 Ti 16G|¥279,980|0.0%|HIGH|rtx 5060 ti|22|direct_structured|
|5|G TUNE DG-A5G60|¥194,800|0.0%|HIGH|rtx 5060|15|direct_structured|
|6|G TUNE FG-A7G70|¥374,800|3.9%|HIGH|rtx 5070|33|direct_structured|
|7|G TUNE FG-A7G7T（TGS2026出展記念モデル第2弾）|¥399,800|10.0%|HIGH|rtx 5070 ti|38|direct_structured|
|8|G TUNE FG-A7G6T|¥406,182|11.4%|REALISTIC|rtx 5060 ti|28|direct_text|
|9|GAMING A18 PRO DXJG3JPBC4JH （英語配列キーボード）|¥419,800|14.2%|REALISTIC|rtx 5070 ti|29|direct_structured|
|10|G TUNE P5-I7G70BK-C（ブラック）|¥448,800|19.8%|REALISTIC|rtx 5070|32|direct_structured|
|11|GALLERIA ZL9R-R57T-6-B|¥738,980|51.3%|VERY_LOW|rtx 5070 ti|40|direct_structured|

## Empirical price-change timing

- Meaningful change sample: **13**
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
- Rows loaded: 194
- Rows appended this run: 5
- Only in-stock/low-stock, exact-identity, direct-structured and PIT-valid observations are added.

## Current buy-now decision

- Status: **公式セール日程の確認待ち** (WAIT_FOR_OFFICIAL_DATES)
- Recommendation: 価格監視は継続中ですが、対象販売店の2026年公式セール日程が未確認です。暫定の広域監視窓だけではBF実売として扱わず、公式日付確認前に購入推奨を出しません。
- Full detail: data/reports/buy-now-now.md
- The timing score is a heuristic priority signal, not a probability forecast.

## Rules
- Missing retrieval is not stockout.
- Seller-internal price-change time is never inferred from article publication time.
- Timing observations are empirical only after sufficient sample size.