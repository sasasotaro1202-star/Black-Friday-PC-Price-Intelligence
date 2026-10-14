# Black Friday PC Price Intelligence — Project Instructions

## 1. Authoritative configuration and user goal

Read `config/targets.json` and `config/build_components.json` before changing budgets, targets, parts, or schedules. They are the authoritative machine-readable configuration; do not reintroduce stale values in prose or code.

The current user-selected plan is:
- **Total cash budget: ¥400,000** for the DIY desktop plus every required peripheral.
- **Peripheral planning target: ¥69,800**; **PC-only planning target/cap: ¥330,200** before any conservative dynamic adjustment for verified delivered peripheral costs. These values sum to ¥400,000.
- Two monitors are required: AOC Q27G40E/11, 27-inch WQHD 180Hz main monitor, and LG 24MS500-B, 23.8-inch FHD IPS 100Hz secondary monitor.
- Speaker target: EDIFIER MR4 MKII. Do not substitute Creative Pebble X or the more expensive MR5 as the main plan without a deliberate, budget-checked update.
- Also budget for Logicool G213r keyboard, Logicool G304 mouse, SteelSeries QcK Large mousepad, ELECOM T-K1A-2625BK power strip, only-needed cables, and shipping/incidentals.
- No headset is in the current purchase list.
- Never count alternate products as simultaneous purchases. Select at most one product per peripheral category, and purchase cables only if included cables are insufficient.

If a user later explicitly changes their total budget or preferred equipment, update the single source of truth and the dependent reports/docs/tests together. Do not silently revert to an older ¥370,000 / one-monitor plan.

## 2. Build method and target configuration

**The primary desktop recommendation must be a self-built DIY PC.** Assembly time and effort are not constraints and receive no penalty. A BTO desktop or laptop may remain in the comparison catalog as a clearly labelled reference benchmark, but must not replace the primary DIY recommendation merely because it avoids assembly.

Primary component target:
- CPU: AMD Ryzen 7 9700X BOX — BF target ¥38,000.
- GPU: PNY GeForce RTX 5070 12GB OC SLIM (exact SKU VCG507012DFSXPB1-O) — BF target ¥129,800; primary balanced gaming target.
- Motherboard: ASRock B850M Pro RS WiFi — ¥20,000.
- Memory: TeamGroup T-CREATE EXPERT White DDR5-6000, 32GB (2×16GB) — ¥40,000.
- SSD: Crucial P3 Plus 1TB NVMe — ¥18,000.
- PSU: Corsair RM850e 2025, 850W ATX 3.1 Gold — ¥14,000.
- Case: Fractal Design Pop Air TG — ¥12,000.
- CPU cooler: Thermalright Peerless Assassin 120 SE V3 — ¥5,000.
- Windows 11 Home retail-license planning allowance — ¥19,360 unless a transferable valid license is explicitly confirmed.
- Component BF target subtotal: ¥296,160; shipping reserve ¥6,000 + small-parts reserve ¥3,000 = **PC target ¥305,160**. With ¥69,800 peripherals, all-in target = **¥374,960**, leaving ¥25,040 against the ¥400,000 target budget.

Keep these alternatives separate and visible:
- **VRAM-focused alternative:** RTX 5060 Ti 16GB exact SKU VCG5060T16DFXPB1-O, source-backed 245×120×39.9mm and 8-pin PCIe connector — BF target ¥109,800; projected all-in target ¥354,960 using the same other targets. Prefer it only when its 16GB VRAM benefits the intended local-AI workload more than the RTX 5070's gaming performance.
- **Dark horse:** RTX 5070 Ti 16GB ARGB (exact SKU VCG5070T16TFXXPB1-O) target ¥154,000; projected all-in target ¥399,160. This is a tight budget case, with only ¥840 target headroom. Exact SKU and manufacturer dimensions are source-backed; the target requires an unusually steep discount versus the ¥207,700 seller listing seen on 2026-10-14 and is an affordability threshold, not a price forecast. Keep purchase authorization closed until live seller price/stock, case clearance for the 2.98-slot card, and final all-in total are verified.
- Do not assume an unquoted RAM/SSD upgrade costs ¥0. Add direct retailer monitor URLs for memory and SSD when an exact-item page is available, and keep unknown/out-of-stock readings explicitly untrusted. The quoted completed configuration must meet **RAM ≥32GB and SSD ≥1TB at purchase**; do not rely on a planned post-purchase upgrade.

The build supports the user's stated mix of Apex Legends, VALORANT, other FPS games, Cities: Skylines II, Python/data analysis, AI-assisted work, and large sports/stock/BTC prediction programs. Explain limits honestly: actual FPS, simulation speed, model capacity and training time depend on settings, datasets and workloads; do not promise specific benchmark results without evidence. Treat GPU VRAM, CPU performance, memory capacity, storage capacity, cooling, power delivery and upgradeability as separate factors.

## 3. Component compatibility and purchasing gate

Keep DIY component prices separate from BTO/laptop offers and peripheral prices. Before marking a build compatible, validate:
- CPU socket and exact board support/BIOS for the selected CPU;
- DDR5 type, 2-stick arrangement, capacity, speed/profile and motherboard memory support/QVL;
- NVMe form factor/interface and M.2 slot constraints;
- motherboard form factor and case support;
- exact GPU SKU dimensions, slot thickness, connector, power draw, PSU capacity/connectors and case clearance;
- CPU cooler socket support and height versus case clearance;
- PSU form factor and required connectors;
- Windows license, shipping, required small parts, and the final complete configuration total.

Exact PNY GPU model codes and dimensions must be maintained from the linked source page; do not reuse one model's specifications for another. Unknown details mean REVIEW, not PASS. Curated `direct_retailer_urls` are still discovery inputs only: the monitor checks up to four configured seller pages (for the primary RTX 5070 this includes Joshin, Sofmap, TSUKUMO and Amazon), compares every successful in-stock offer, then selects the lowest eligible price; only the direct-page identity, price, stock and PIT verifier can mark a listing verified. When a DIY purchase gate is blocked, its reason must describe the actual blocker (component references, compatibility, budget or checkout validation), not merely repeat that DIY is the selected method. Even if an automated mechanical check says PASS, verify manufacturer documentation for the exact SKU and the retailer's final basket immediately before purchase.

## 4. Budget and price semantics

`config/targets.json` is the budget source of truth; `config/build_components.json` is the DIY component source of truth. Preserve this invariant:

`total_budget_jpy = peripheral_budget_jpy + pc_target_jpy`

The peripheral BF targets should total ¥69,800. Primary DIY parts, shipping reserve and small-parts reserve should total ¥305,160. The main DIY all-in target is ¥374,960. Dynamic PC spending cap may be reduced based on **fresh, model-matched, in-stock, delivered peripheral prices**. A missing/stale/unknown peripheral price or inventory status is not evidence of a deal: use configured targets only as a planning estimate, mark readiness incomplete and keep the overall purchase gate closed.

Every price must be labelled as one of:
- **BF purchase target**: desired price, not a forecast and not observed.
- **Pre-BF/current reference**: reference only; not a BF actual.
- **Verified market reference**: comparison-site listing, not a checkout offer.
- **Direct retailer listing reference**: exact-model page price, but still not necessarily in-stock or final checkout price.
- **Verified checkout cash price**: seller, exact SKU, configuration, stock, shipping/mandatory fees, discounts and final cash amount checked.
- **Verified BF-period price**: eligible only when the retailer's official 2026 campaign dates are confirmed, the observation falls inside that retailer's official period, exact product/configuration and stock are verified, checkout terms are clear, and point-in-time (PIT) evidence is valid.

Do not call a price “BF actual” just because it was observed in the broad watch window or within the initial planning focus of 2026-11-14 through 2026-12-04. The configured broad observation window is **2026-11-01 00:00 JST to 2026-12-11 23:59:59 JST**; this is not a retailer's official BF period. That initial focus range is a planning horizon only. Resolve each retailer's actual 2026 sale interval independently from official, year-specific evidence; never infer it from 2025 dates, weekday patterns or month/day text without a year.

Unknown prices must stay null/unknown—not ¥0. Fetch failure is not out-of-stock. Keep listed price, reference price, checkout cash amount, delivery, fees, coupons, points, lottery benefits and future rewards separate. Deduct only benefits confirmed applicable at checkout from the immediate cash total.

## 5. Monitoring, data integrity and free operation

- Normal scheduled monitoring: about every 15 minutes.
- During the configured provisional broad watch window: about every 5 minutes.
- `.github/workflows/pc-price-monitor.yml` owns scheduled price collection. It routes between the 5-minute and 15-minute cron events according to the configured window; keep the gate and intervals consistent with `config/targets.json`.
- `.github/workflows/pc-price-monitor-bf-fast.yml` is manual-only, shares the single writer concurrency group, and must not create a second scheduled collection loop.
- Use GitHub Actions and the Python standard library first. No paid API or service may be required. Do not add hidden paid dependencies, keys, or usage-based services.
- Include Yahoo! Shopping (`shopping.yahoo.co.jp`) among allowlisted retailer search fallbacks; treat search-result prices as discovery-only until the exact seller item page is independently fetched and validated.
- Keep PC offers, DIY component observations, and peripherals in separate streams. Never rank a monitor/speaker/mouse as a PC.
- Preserve source URL, exact model/SKU evidence, retrieval time, availability time, publication/event times when known, inventory state, data age, validation reason, and source snapshot hashes.
- Require valid PIT ordering: `available_at <= retrieval_time <= prediction_time`. If PIT is unknown or invalid, fail closed.
- Direct retailer listings and comparison-site results are different evidence classes; a search-result snippet is display-only unless exact-model identity and other validation rules pass.
- Show retrieval coverage, failed hosts/reasons, rejected SKU matches, unverified prices, and unknown inventory explicitly. Do not improve apparent coverage by loosening identity, stock, freshness, or PIT rules.

## 6. Ranking and decision quality

The 100-point score is **purchase priority, not probability**. Use the configured weighting: performance 40, price/value 20, historical sale evidence 15, stock/sellout risk 15, and timing 10. Never describe this score as the probability of a discount, a price fall, or winning a deal.

A recommendation must consider the **full PC + peripheral all-in cost**, the exact completed configuration, real stock, return/warranty risk, part quality, cooling, noise where evidence exists, upgradeability, source quality, and observed-data freshness. A build can remain a monitored candidate while its purchase gate is closed. Do not issue purchase authorization if price, model identity, stock, official sale dates, completed RAM/SSD configuration, compatibility, or all-in cash total is unresolved.

The output must make the current decision easy to read on a phone: leading DIY build, 16GB-VRAM alternative, RTX 5070 Ti dark horse, PC-only total, accessory total, all-in total, remaining budget, target versus latest verified evidence, inventory/compatibility blockers, and a clear BUY / WAIT / REVIEW decision. Never imply that a BF target is already available today.

## 7. Development and autonomous improvement

For each safe/free defect: observe → diagnose → implement → add/adjust regression tests → validate data and PIT → check generated reports → merge/promote only when checks pass → monitor again. Prefer a branch and pull request rather than unreviewed direct edits to `main`. Do not weaken a gate simply to force a BUY_NOW answer.

Tests should be network-independent where possible and cover:
- all-in budget arithmetic and accessory target totals;
- config/build-profile agreement and one-GPU-only subtotal logic;
- RAM/SSD minimums and model-specific unknown compatibility;
- target/reference/checkout/BF price separation;
- official campaign date and PIT fail-closed behavior;
- the cron gate's 5-minute/15-minute routing and manual-only fast workflow;
- current README, Copilot instructions and peripheral guide staying aligned with the authoritative config.

Run `python -m unittest discover -s tests -p "test_*.py" -v`, Python compile checks, `scripts/self_build_planner.py`, report/timing/scenario generation, `scripts/healthcheck.py`, `scripts/validate.py`, and `git diff --check` before promoting relevant changes. Report actual verification results; do not claim a test passed until its CI run confirms it.
