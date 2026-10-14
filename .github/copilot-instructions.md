# Black Friday PC Price Intelligence — Project Instructions

## 0. Product operating contract: GitHub collects evidence; ChatGPT gives the final answer

The user's intended workflow is explicit:
- GitHub Actions is the continuous, free-first **collection, history, verification, and data-quality system**. Collect evidence in advance so it is available when the user returns.
- Generated rankings, scores, buy-timing opinions, build plans and Markdown reports are **internal diagnostic/index artifacts**, not the final user-facing recommendation. Do not treat them as authoritative just because they were generated successfully.
- When the user asks for a ranking or detailed advice in ChatGPT, use the newest committed data, inspect timestamps/coverage/error logs, and independently verify decision-critical prices, stock, exact SKU, current offers, and official campaign dates with fresh sources where possible. Build the final comparison for the budget and preferences in the latest user request.
- Preserve historical observations, exact item identity, merchant/source URL, price semantics, stock state, retrieved/available/published times, PIT validity, and rejection/error diagnostics. Unknown is a valid state; invented completeness is not.
- A site can block retrieval or omit fields. Define “complete data” as broad tracked coverage with explicit gaps, retries, and source-quality evidence—not a promise that every retailer will always be readable.
- Never present a GitHub-produced 100-point priority score as a discount probability or as the finished answer. On-demand ChatGPT output should explain what evidence changed the ranking and distinguish target thresholds from verified BF offers and final checkout cash amounts.

## 1. Authoritative configuration and user goal

Read `config/targets.json` and `config/build_components.json` before changing budgets, targets, parts, or schedules. They are the authoritative machine-readable configuration; do not reintroduce stale values in prose or code.

The current user-selected plan is:
- **Total-system planning target: around ¥400,000** for the DIY desktop plus every required peripheral. Treat this as the center target, not a reason to omit dark horses from rankings; list any overrun explicitly.
- **Peripheral planning target: ¥69,800**; **PC-only planning frame: ¥330,200** before the conservative dynamic adjustment for verified delivered peripheral costs. These target values sum to ¥400,000.
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
- Primary budget-fit memory target: TeamGroup T-CREATE EXPERT DDR5-6000 32GB (2×16GB), target ¥40,000. Keep Crucial Pro DDR5-6000 32GB (2×16GB), model CP2K16G60C36U5W, at a ¥60,000 BF target as a separately tracked alternative. Select between them only on fresh exact-item evidence and verified final configuration; the exact motherboard QVL/BIOS remains a pre-purchase gate.
- SSD: Crucial P3 Plus 1TB NVMe — ¥18,000.
- PSU: Corsair RM850e 2025, 850W ATX 3.1 Gold — ¥14,000.
- Case: Fractal Design Pop Air TG — ¥12,000.
- CPU cooler: Thermalright Peerless Assassin 120 SE V3 — ¥5,000.
- Windows 11 Home Japanese boxed retail package (SKU HAJ-00094) — BF target ¥14,800; monitor the direct Yodobashi offer and the exact comparison item. Do not use a stale manual ¥19,360 amount as a live market price.
- TeamGroup-based component BF target subtotal: ¥291,600; shipping reserve ¥6,000 + small-parts reserve ¥3,000 = **PC target ¥300,600**. With ¥69,800 peripherals, all-in target = **¥370,400**, leaving a planned ¥29,600 buffer against the around-¥400,000 target. A Crucial-memory version is ¥320,600 PC / ¥390,400 all-in, leaving ¥9,600 under the ¥400,000 target. These are desired BF prices, not forecasts or verified prices.

Keep these alternatives separate and visible:
- **VRAM-focused alternative:** RTX 5060 Ti 16GB exact SKU VCG5060T16DFXPB1-O — with the ¥40,000 TeamGroup memory target, projected PC cost ¥280,600 / all-in target ¥350,400. If the Crucial kit is chosen instead, the all-in target is ¥370,400. Keep the local-AI 16GB VRAM advantage distinct from gaming-performance comparisons; re-check the exact GPU's dimensions, connector and completed build.
- **Dark horse:** RTX 5070 Ti 16GB ARGB (exact SKU VCG5070T16TFXXPB1-O), BF GPU target ¥154,000. With TeamGroup memory, projected PC cost is ¥324,800 / all-in target **¥394,600**, leaving ¥5,400 under the ¥400,000 center target; with Crucial memory, all-in target is ¥414,600. **Always include it in final rankings as a stretch candidate**, show the overrun and price reduction needed, and keep case clearance for its 2.98-slot thickness as REVIEW. A target is not a price forecast. Do not authorize purchase until live seller price/stock, case clearance, compatibility and final all-in cash total are verified.
- Do not assume an unquoted RAM/SSD upgrade costs ¥0. Add direct retailer monitor URLs for memory and SSD when an exact-item page is available, and keep unknown/out-of-stock readings explicitly untrusted. The quoted completed configuration must meet **RAM ≥32GB and SSD ≥1TB at purchase**; do not rely on a planned post-purchase upgrade.

The build supports the user's stated mix of Apex Legends, VALORANT, other FPS games, Cities: Skylines II, Python/data analysis, AI-assisted work, and large sports/stock/BTC prediction programs. Explain limits honestly: actual FPS, simulation speed, model capacity and training time depend on settings, datasets and workloads; do not promise specific benchmark results without evidence. Treat GPU VRAM, CPU performance, memory capacity, storage capacity, cooling, power delivery and upgradeability as separate factors.

## 3. Component compatibility and purchasing gate

Keep DIY component prices separate from BTO/laptop offers and peripheral prices. Before marking a build compatible, validate:
- CPU socket, exact manufacturer CPU-support-list entry, required BIOS version and the actual shipped/installed board BIOS;
- DDR5 type, 2-stick arrangement, capacity, speed/profile and the exact memory kit's motherboard QVL entry;
- NVMe form factor/interface and M.2 slot constraints;
- motherboard form factor and case support;
- exact GPU SKU dimensions, slot thickness, connector, power draw, PSU capacity/connectors and case clearance;
- CPU cooler socket support and height versus case clearance;
- PSU form factor and required connectors;
- Windows license, shipping, required small parts, and the final complete configuration total.

Exact PNY GPU model codes and dimensions must be maintained from the linked source page; do not reuse one model's specifications for another. Unknown details mean REVIEW, not PASS. The current default build must remain REVIEW until the B850M Pro RS WiFi's actual BIOS is checked against the official Ryzen 7 9700X minimum BIOS (3.12) and the exact selected memory kit is confirmed in the motherboard QVL. General socket support and DDR5/EXPO support do not substitute for those checks. Curated `direct_retailer_urls` are still discovery inputs only: the monitor checks each configured exact seller page (the primary RTX 5070 currently has Joshin, Sofmap and TSUKUMO candidates), compares every successful in-stock offer, then selects the lowest eligible price; do not keep a seller URL whose primary page title/product identity mismatches the intended SKU. only the direct-page identity, price, stock and PIT verifier can mark a listing verified. When a DIY purchase gate is blocked, its reason must describe the actual blocker (component references, compatibility, budget or checkout validation), not merely repeat that DIY is the selected method. Even if an automated mechanical check says PASS, verify manufacturer documentation for the exact SKU and the retailer's final basket immediately before purchase.

## 4. Budget and price semantics

`config/targets.json` is the budget source of truth; `config/build_components.json` is the DIY component source of truth. Preserve this invariant:

`total_budget_jpy = peripheral_budget_jpy + pc_target_jpy` (the configured center target is ¥400,000; keep over-target candidates in comparisons but do not silently approve spending above the target).

The peripheral BF targets should total ¥69,800. The TeamGroup-based main DIY parts, shipping and small-parts target should total ¥300,600, producing a ¥370,400 all-in planning target. Crucial Pro CP2K16G60C36U5W at ¥60,000 remains an alternative with a ¥390,400 all-in target. Keep RTX 5070 Ti at ¥394,600 all-in with TeamGroup as an over-target stretch candidate. Rankings must preserve these options and show deltas; purchase authorization remains fail-closed until fresh price, stock, compatibility and checkout evidence pass.

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
- For Ryzen 7 9700X, monitor both Yodobashi and the exact TSUKUMO item page (SKU 100-100001404WOF). For ASRock B850M Pro RS WiFi, monitor both Yodobashi and PC4U. Direct price and inventory are re-fetched on every run; indexed values are never automatically promoted.
- Show retrieval coverage, failed hosts/reasons, rejected SKU matches, unverified prices, and unknown inventory explicitly. Do not improve apparent coverage by loosening identity, stock, freshness, or PIT rules.

## 6. Data products versus final on-demand ranking

The 100-point score is **an internal purchase-priority index, not a probability and not the user's final recommendation**. Use the configured weighting for diagnostics only: performance 40, price/value 20, historical sale evidence 15, stock/sellout risk 15, and timing 10. Never describe it as the probability of a discount or price fall.

The monitoring pipeline may build internal data views to test consistency and expose gaps. The final ranking is produced in ChatGPT only when the user asks. At that time:
- Start with the user's latest explicit budget/preferences, not an older README target if the conversation has changed them.
- Read source data and generation/retrieval timestamps before relying on any derived JSON or Markdown ranking.
- Verify critical current seller pages, exact SKU, stock, final cash price, shipping, coupon eligibility and official campaign dates independently where possible. Do not represent pre-BF snapshots or comparison-site references as observed BF prices.
- Produce all relevant requested rankings separately: overall PC/build options, individual DIY component alternatives, each peripheral category, and outliers/dark horses. Include direct product links, budget arithmetic, what is confirmed versus target-only, sellout risk, and compatibility gaps.
- Consider the **full PC + peripheral all-in cost**, exact configuration, real stock, warranty/return risk, part quality, cooling, upgradeability, source quality and freshness. If any gating evidence is unresolved, label the item for monitoring/review rather than authorizing purchase.

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


## Direct seller coverage refresh — 2026-10-14
- TeamGroup DDR5-6000 32GB exact model CTCWD532G6000HC38ADC01 must use the linked official manufacturer page for specification identity, not as a price source. Keep YMall as an untrusted seller candidate unless exact SKU, direct price, stock and PIT verify.
- Crucial P3 Plus CT1000P3PSSD8JP 1TB is monitored at TSUKUMO and Dospara; Dospara may list a price while out-of-stock, which remains reference-only.
- Fractal Pop Air FD-C-POA1A-02 is monitored at Yodobashi and Dospara. Use the direct fetched product page to verify stock and shipping; never infer buyability from search-card text.


## Motherboard direct-price fallback — 2026-10-14
- ASRock B850M Pro RS WiFi has a third exact-model seller page at Sofmap `https://www.sofmap.com/product_detail.aspx?sku=101393495`. A listing found in search showed ¥21,380 and an in-stock/24-hour dispatch label; these are discovery evidence, not a verified current checkout price. The scheduled direct-page monitor must independently validate the actual SKU, price, stock, and PIT before promotion.
