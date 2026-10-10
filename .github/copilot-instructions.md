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
