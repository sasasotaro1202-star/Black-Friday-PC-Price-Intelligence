# Black Friday PC Price Intelligence — Project Instructions

## Goal
Evaluate the best Japanese-market PC purchase throughout the entire 2026 Black Friday window. Desktops are preferred, but do not discard exceptional laptop, outlet, old-stock, or limited-time deals. A bargain is only current when supported by recent source evidence.

## Authoritative all-in budget
config/targets.json is the single source of truth.

- Total budget: JPY 370,000 for PC + all required peripherals.
- Peripheral target allocation: JPY 67,800.
- PC target price: JPY 299,800.
- PC planned hard cap: JPY 302,200 only when all peripherals stay within their target allocation.
- Required PC configuration: RAM >= 32GB and SSD >= 1TB.
- One monitor only; no secondary monitor and no headset.
- Sound quality is important: EDIFIER MR5 is the preferred speaker target; compare MR4 MKII or other alternatives when appropriate.
- Include shipping, required fees, cable needs, and multi-store shipping reserve.
- Track monitor, speakers, mouse and mousepad prices separately from PC prices.
- Do not subtract coupons, points, lotteries, future rewards, or eligibility-dependent perks until actual checkout applicability is verified.

## Black Friday price semantics — mandatory

- All purchase target prices in the 37万円 strategy and peripheral targets mean **prices targeted for purchase during the Black Friday window**, not today's prices.
- Window: 2026-11-14 00:00 JST through 2026-12-04 23:59 JST.
- Before the window, listings are `PRE_BLACK_FRIDAY_REFERENCE`; they must not populate `black_friday_price_observed_jpy` or be described as BF sale prices.
- A BF-period observation requires source retrieval inside the window, verified current price, SKU identity, valid PIT, and confirmed stock.
- Show BF target price, pre-window reference price, and observed BF-window price separately. Never present a future sale price as confirmed.
- ¥299,800 PC target, ¥302,200 planned cap and ¥32,000 MR5 target are BF purchase goals. Use actual peripheral prices to adjust the PC cap only during the BF window and when the accessory snapshot is fresh and verified.

## 37万円購入戦略

- Primary conditional target: `desktop-gtune-dg-i5g70-5070`. Its 279,800 JPY listing is only the 16 GB / 500 GB baseline. Never mark it purchase-ready until a 32 GB / 1 TB completed configuration and checkout price are verified. For a 279,800 JPY baseline, the max upgrade allowance is 20,000 JPY to reach the 299,800 JPY PC target or 22,400 JPY to reach the 302,200 JPY planning cap; these are arithmetic ceilings, not quoted upgrade prices.
- Secondary complete-build watch: the exact outlet SKU `DGA7G70B5BBDW101DECWA`, official URL `https://www.mouse-jp.co.jp/store/g/ggtune-dga7g70b5bbdw101decwa/`. The 2026-10-10 observed listing reference was 304,800 JPY with Ryzen 7 5700X, RTX 5070, 32 GB RAM and 1 TB SSD. Always refresh price, inventory and SKU identity before treating it as current.
- Outlier watch: RTX 5070 Ti desktop with at least 32 GB RAM / 1 TB SSD is eligible only if its directly verified completed build price is within the live dynamic PC cap. No assumed-zero upgrade costs.
- Keep EDIFIER MR5 at a 32,000 JPY target. Coupons are not deducted until final checkout applicability is verified.
- Do not hardcode the illustrative 96/94/95/97 scores. Compute the actual priority score from validated live evidence, and keep purchase gates closed whenever completed configuration or price is unknown.

Current prices of tracked peripherals must adjust the dynamic PC cap. Missing/stale price or unknown stock must use the configured target as a planning reserve only and keep the overall purchase gate closed.

## Decision score
The 100-point score is purchase priority, not probability. Weight: performance 40, price/value 20, historical sale evidence 15, stock/sellout risk 15, timing 10. Include GPU/VRAM, CPU, memory, SSD, cooling, PSU/expandability, configuration, warranty, source quality, data freshness, variant identity and PIT validity.

A PC with fewer than 32GB RAM or less than 1TB SSD must be NEEDS_CONFIGURATION, never BUY_NOW. Never price an unquoted memory/storage upgrade as zero. Use completed configuration cost.

## Fail-closed evidence rules
Fail closed on missing current price, ambiguous SKU, conflicting CPU/GPU/RAM/SSD evidence, unknown stock when purchaseability matters, stale observations, missing/invalid PIT, conflicting structured prices, anomalous prices without independent corroboration, or reference/monthly/installment/discount amounts mistaken for actual sale price.

Keep current price, historical/reference price, mandatory shipping/fees, confirmed cash benefit, conditional benefits and planning targets separate. Fetch failure is not out-of-stock. A historical price is not a current offer. Shared model-family pages are not proof of exact SKU.

Preserve event_time, publication_time, available_at, retrieval_time and prediction_time. Unknown event_time remains null. Require available_at <= retrieval_time <= prediction_time; unknown/invalid PIT means no purchase recommendation.

## Workflow design
- Normal monitoring executes about every 15 minutes.
- Black Friday window monitoring executes about every 5 minutes.
- Use a single scheduled workflow; keep the fast workflow manual-only to prevent duplicated runs.
- Never cancel an in-progress price collection when a newer cron tick arrives; use `cancel-in-progress: false` for the shared writer concurrency group.
- Run `scripts/discover.py` only after syncing/resetting to the latest `origin/main` inside the publish retry loop; otherwise the reset discards the newly discovered watchlist.
- Monitor PCs and accessories separately; accessory prices must never appear as PC ranking rows.
- GitHub Actions and Python standard library first. No paid APIs or unknown billing dependencies.
- Validate budget arithmetic, accessory target sum, complete PC configuration, dynamic all-in PC cap, SKU identity, price source, stock, coverage counters, source snapshot hash, scoring arithmetic and PIT before publishing.
- Run tests and healthcheck before promoting changes. Never weaken safety gates to force a recommendation.

## Autonomous improvement
For each safe/free defect: observe → diagnose → implement → unit/regression tests → PIT/data-quality validation → promote or rollback → monitor again. Report evidence, uncertainty and exact uncompleted work honestly.

## Window
Broad watch window: 2026-11-14 00:00 JST through 2026-12-04 23:59 JST until official retailer-specific dates are independently verified.


## Free source resilience and diagnostics

- Use free public search providers in sequence when a direct page request fails; do not require API keys or paid services.
- A search result's price is usable only when that result title/snippet contains a catalogued exact SKU/model alias, the URL host is on the allowlist, the price passes bounds validation, and the source is preserved for audit. Never infer SKU identity solely from the canonical product URL.
- Preserve request failure details (HTTP status, curl exit/status code, timeout/connect reason), grouped by host and reason. Do not treat transport errors as stockout or a sale.
- Keep search attempts, accepted fallback observations and rejected SKU matches separate in the report.
- Limit concurrent requests to avoid raising merchant-side throttling. Do not improve metrics by weakening the identity, stock, freshness, or PIT gates.
- For any PC missing 32 GB RAM or 1 TB SSD, leave the completed-build discount percentage uncomputed until the completed configuration price is known.


## Alternate direct product sources

- The canonical product URL remains the user-facing purchase link. Optional `alternate_price_urls` are measurement/evidence sources only, and must be curated for the same SKU/model.
- Try the canonical URL first. Try registered alternate URLs only if the canonical fetch or price parse fails.
- An alternate page must contain a catalogued exact SKU/model alias and have non-contradictory parsed identity/specs before any price is accepted.
- Log every attempted source, the actual source URL, failure reason, and whether the alternate was accepted. Preserve these diagnostics through sanitization and include them in the report.
- Use HTTP/1.1 as a curl transport compatibility fallback to reduce HTTP/2 stream failures; this is a transport retry, not a reason to bypass host, SKU, price, inventory, or PIT validation.
