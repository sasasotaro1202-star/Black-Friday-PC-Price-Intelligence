# Black Friday price timing analysis

Generated: 2026-11-04T11:17:13+09:00
Source snapshot: 2026-11-04T11:10:23+09:00
Source snapshot SHA256: 3580aeb6c0a9759d35cceb33d73e5a0db2a80d686a9114b316aba38e5cb44920
Budget: ¥360,000
U.S. Black Friday calendar reference only (not official retailer sale dates): 2026-11-27

## Completed-PC / BTO benchmark references (not DIY purchase candidates)

The primary purchase method is self-build. These completed-PC listings are price/performance benchmarks only; they do not authorize a purchase and must not be used as component prices or as the DIY build's checkout total.

|Rank|Completed-PC reference model|Current reference price|Required drop to target|Reference feasibility|GPU|Perf|Source|
|---:|---|---:|---:|---|---|---:|---|
|1|THIRDWAVE AD-R7A56C-0AW (Ryzen 7 7700 / RTX 5060 Ti 16G|¥279,980|0.0%|HIGH|rtx 5060 ti|22|direct_structured|
|2|GAMING A18 PRO DXJG3JPBC4JH （英語配列キーボード）|¥419,800|14.2%|REALISTIC|rtx 5070 ti|29|direct_structured|
|3|GALLERIA ZL9R-R57T-6-B|¥738,980|51.3%|VERY_LOW|rtx 5070 ti|40|direct_structured|

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
- Rows loaded: 188
- Rows appended this run: 1
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