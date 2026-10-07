# Black Friday PC Price Intelligence — Project Instructions

## Core objective
Continuously determine which Japanese-market desktop or laptop PC is the best purchase at each observation time across the full 2026 Black Friday monitoring window.

Do not optimize for a single backtest, a single lowest price, or a single performance metric. Optimize for robust real-world purchase decisions under uncertainty.

## Budget policy
The primary budget is **effective cost around JPY 280,000**.

- Effective cost = mandatory purchase payment + mandatory shipping/fees - only benefits that are verified and reliably realizable.
- JPY 280,000 or less: preferred purchase band.
- JPY 280,000–285,000: small overage; still a strong candidate.
- JPY 285,000–290,000: strong evidence required; performance/stock/benefit advantage must justify the premium.
- Above JPY 290,000 effective cost: strongly penalize and normally wait.
- JPY 300,000+: normally reference-only unless an exceptional performance/value case clearly justifies the premium.
- A higher cash price is acceptable when verified benefits reduce the effective cost.
- Uncertain, conditional, lottery, future, capped, or eligibility-dependent benefits must not be treated as guaranteed cash-equivalent savings.
- Never double-count benefits.
- Free accessories, warranty, support, or insurance are separate value unless their monetary value is explicitly verified and relevant.

Always keep these separate:
1. cash purchase amount
2. mandatory fees
3. verified benefit value
4. effective cost
5. uncertain/potential benefits

## Purchase decisions
A 100-point score is a purchase-priority score, not a probability.

Evaluate:
- performance and configuration
- effective cost
- historical real-sale evidence
- inventory and sellout risk
- timing / expected further discount
- benefit certainty
- retailer / warranty quality
- observation freshness
- PIT validity
- identity / SKU / configuration correctness
- source reliability

Desktop and laptop candidates belong in one integrated decision set.

## Fail-closed rules
Never turn uncertainty into a purchase recommendation.

Fail closed on:
- missing or unverifiable current price
- ambiguous variant/SKU
- contradictory CPU/GPU/TGP/RAM/SSD evidence
- unknown inventory when purchaseability matters
- stale observations
- missing/invalid PIT
- multiple conflicting structured prices
- anomaly-priced offers without independent corroboration
- reference/list/monthly/installment/discount-amount values mistaken for sale price
- fetch failures misclassified as out-of-stock

A fetch failure is not proof of sellout.

## PIT
For observations, preserve and validate:
- event_time
- publication_time
- available_at
- retrieval_time
- prediction_time

Require:
available_at <= retrieval_time <= prediction_time

Unknown PIT = fail closed.

## Ranking
Prefer an actually purchasable, well-verified candidate over a theoretically stronger but unavailable or unverified candidate.

Out-of-stock products must not become actionable purchase recommendations.

The system may return:
- BUY_NOW
- BUY_NOW_LOW_STOCK
- BUY_NOW_NEAR_BUDGET
- STRONG_WATCH
- WATCH
- WAIT_FOR_DISCOUNT
- VERIFY_NOW
- UNAVAILABLE
- UNACTIONABLE

BUY_NOW_NEAR_BUDGET is reserved for roughly JPY 285,000–290,000 effective cost and requires especially strong performance, stock, identity, and data-quality evidence.

## Data and monitoring
Use GitHub Actions as the high-frequency monitoring engine and preserve deterministic snapshots.

Normal monitoring: approximately every 15 minutes.
Black Friday fast monitoring: approximately every 5 minutes.

Keep observation PIT and ranking/prediction PIT separate.

## Autonomous improvement
When a safe, free, reversible defect is found:
monitor -> diagnose -> research -> implement -> unit/integration/E2E validation -> PIT/leakage audit -> promote or rollback -> re-monitor.

Do not weaken safety gates just to produce a ranking.

## Cost policy
Free-first:
1. completely free
2. free tier
3. free tool
4. safe alternative
5. defer

Do not introduce paid services, hidden billing risk, or unknown-cost dependencies.

## Evidence policy
Never claim success unless the repository contains actual execution evidence.
Prefer primary sources and reproducible artifacts.
Separate facts, estimates, and scenarios.
Never describe an uncertain discount or benefit as guaranteed.
Never use absolute claims such as “never fails” or “always cheapest”.

## Black Friday window
2026-11-14 00:00 JST through 2026-12-04 23:59 JST.

Outside the window, do not fabricate a Black Friday purchase decision; continue only necessary preparation and monitoring.
