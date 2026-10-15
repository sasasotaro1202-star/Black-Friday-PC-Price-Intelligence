#!/usr/bin/env python3
"""Analyze curated public BF historical sources without inferring unsupported forecasts."""
import csv, json, os, statistics
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMPAIGNS = os.path.join(ROOT, "data", "historical_bf_campaigns.json")
DEALS = os.path.join(ROOT, "data", "historical_bf_deals.csv")
OUT_JSON = os.path.join(ROOT, "data", "historical_bf_analysis.json")
OUT_MD = os.path.join(ROOT, "data", "reports", "historical-bf-analysis.md")
JST = timezone(timedelta(hours=9))

def now_iso():
    return datetime.now(JST).isoformat(timespec="seconds")

def pct_discount(reference, sale):
    if not reference or not sale or float(reference) <= 0:
        return None
    return round((float(reference) - float(sale)) / float(reference) * 100.0, 1)

def load_records():
    with open(CAMPAIGNS, encoding="utf-8") as f:
        campaigns = json.load(f)
    with open(DEALS, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required_columns = {
            "year", "event_date", "channel", "retailer", "category",
            "product", "sale_price_jpy", "source_url", "source_grade",
        }
        if not required_columns.issubset(set(reader.fieldnames or [])):
            raise ValueError(f"historical BF CSV missing required columns: {sorted(required_columns - set(reader.fieldnames or []))}")
        deals = list(reader)
    seen_keys = set()
    for row_number, row in enumerate(deals, start=2):
        if None in row:
            raise ValueError(f"malformed historical BF CSV row {row_number}: extra columns")
        missing = [k for k in ("year", "event_date", "channel", "retailer", "category", "product", "sale_price_jpy", "source_url", "source_grade") if not str(row.get(k) or "").strip()]
        if missing:
            raise ValueError(f"historical BF CSV row {row_number} missing required values: {missing}")
        row["year"] = int(row["year"])
        try:
            event_date = datetime.strptime(row["event_date"], "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(f"invalid event_date in historical BF CSV row {row_number}: {row['event_date']}") from exc
        if event_date.year != row["year"]:
            raise ValueError(f"year/event_date mismatch in historical BF CSV row {row_number}")
        key = (row["year"], row["event_date"], row["channel"], row["retailer"], row["model"], row["product"])
        if key in seen_keys:
            raise ValueError(f"duplicate historical BF observation row {row_number}: {key}")
        seen_keys.add(key)
        for k in ("sale_price_jpy", "reference_price_jpy", "discount_jpy", "discount_pct", "ram_gb", "ssd_gb"):
            val = row.get(k)
            row[k] = float(val) if val not in (None, "") else None
        if row["sale_price_jpy"] is None or row["sale_price_jpy"] <= 0:
            raise ValueError(f"invalid sale price: {row.get('product')}")
        if not str(row.get("source_url") or "").startswith("https://"):
            raise ValueError(f"missing https source: {row.get('product')}")
        computed = pct_discount(row["reference_price_jpy"], row["sale_price_jpy"])
        if computed is not None and row["discount_pct"] is not None and abs(computed-row["discount_pct"]) > 1.1:
            raise ValueError(f"discount arithmetic mismatch: {row.get('product')}: {computed} vs {row['discount_pct']}")
        if row["reference_price_jpy"] is not None and row["discount_jpy"] is not None:
            delta = int(row["reference_price_jpy"] - row["sale_price_jpy"])
            if abs(delta - row["discount_jpy"]) > 1:
                raise ValueError(f"discount amount mismatch in historical BF CSV row {row_number}: {row.get('product')}")
    return campaigns, deals

def summarize(campaigns, deals):
    crows = campaigns["campaigns"]
    years = sorted({int(x["year"]) for x in crows})
    retailer_years = {}
    for c in crows:
        key = f'{c["retailer"]} / {c["year"]}'
        retailer_years.setdefault(key, []).append({
            "channel": c["channel"], "start_jst": c.get("start_jst"),
            "end_jst": c.get("end_jst"), "source_grade": c["source_grade"],
            "source_url": c["source_url"]
        })
    by_category = {}
    for d in deals:
        category = d["category"]
        b = by_category.setdefault(category, {"records":0, "with_reference_price":0,
            "sale_prices_jpy":[], "discount_examples":[], "source_grades":{}, "comparability_groups":{}})
        b["records"] += 1
        b["sale_prices_jpy"].append(int(d["sale_price_jpy"]))
        b["source_grades"][d["source_grade"]] = b["source_grades"].get(d["source_grade"], 0) + 1
        if d["reference_price_jpy"] is not None:
            b["with_reference_price"] += 1
            comp = str(d.get("comparability_group") or "")
            b["comparability_groups"][comp] = b["comparability_groups"].get(comp, 0) + 1
            b["discount_examples"].append({
                "year":d["year"], "retailer":d["retailer"], "product":d["product"],
                "sale_price_jpy":int(d["sale_price_jpy"]),
                "reference_price_jpy":int(d["reference_price_jpy"]),
                "discount_pct":pct_discount(d["reference_price_jpy"],d["sale_price_jpy"]),
                "source_grade":d["source_grade"], "source_url":d["source_url"],
                "notes":d["notes"], "comparability_group":comp
            })
    for b in by_category.values():
        vals=b.pop("sale_prices_jpy")
        b["sale_price_range_jpy"]={"min":min(vals),"max":max(vals)}
        b["discount_examples"].sort(key=lambda r:(r["year"],r["discount_pct"] or 0))
        # Estimate a "typical" rate only when at least 3 independent observations
        # share a defined like-for-like class. This dataset intentionally avoids
        # grouping dissimilar products into a false common discount average.
        adequate=[]
        for group,count in b["comparability_groups"].items():
            if group and count >= 3:
                adequate.extend(x["discount_pct"] for x in b["discount_examples"]
                                if x["comparability_group"]==group and x["discount_pct"] is not None)
        b["comparable_discount_sample_count"]=len(adequate)
        b["comparable_discount_median_pct"]=round(statistics.median(adequate),1) if len(adequate)>=3 else None
        if not b["comparability_groups"].get("", 0):
            b["comparability_groups"].pop("", None)
    return {
        "schema_version":1, "generated_at":now_iso(),
        "source_policy":"Campaign dates are taken from retailer official sources where available; secondary sources are flagged. Sale-price samples are source-dated observations, not guarantees of historical lowest price. No 2026 price probability is inferred from this sparse, heterogeneous sample.",
        "campaign_years_covered":years, "campaign_record_count":len(crows),
        "retailer_year_channel_records":retailer_years,
        "historical_deal_record_count":len(deals),
        "source_grade_counts":{g:sum(1 for d in deals if d["source_grade"]==g) for g in sorted({d["source_grade"] for d in deals})},
        "price_observations":[
            {
                "year":d["year"], "event_date":d["event_date"], "channel":d["channel"],
                "retailer":d["retailer"], "category":d["category"], "product":d["product"],
                "model":d.get("model") or None,
                "sale_price_jpy":int(d["sale_price_jpy"]),
                "reference_price_jpy":int(d["reference_price_jpy"]) if d["reference_price_jpy"] is not None else None,
                "discount_jpy":int(d["discount_jpy"]) if d["discount_jpy"] is not None else None,
                "discount_pct":pct_discount(d["reference_price_jpy"],d["sale_price_jpy"]),
                "cpu":d.get("cpu") or None, "gpu":d.get("gpu") or None,
                "ram_gb":int(d["ram_gb"]) if d["ram_gb"] is not None else None,
                "ssd_gb":int(d["ssd_gb"]) if d["ssd_gb"] is not None else None,
                "source_url":d["source_url"], "source_published_at":d.get("source_published_at") or None,
                "source_grade":d["source_grade"], "comparability_group":d.get("comparability_group") or None,
                "notes":d.get("notes") or ""
            }
            for d in sorted(deals, key=lambda x:(x["year"], x["event_date"], x["retailer"], x["product"]))
        ],
        "categories":by_category,
        "forecast_policy":{"2026_official_dates_inferred":False,"probability_model_enabled":False,
          "typical_discount_only_if_like_for_like_n_at_least":3,
          "why_not_forecast":"The historical set mixes generations, SKUs, BTO vs DIY, list prices vs observations, and source types. It supports price ranges and purchase timing context, not a calibrated probability of a specific 2026 price."}
    }

def render_md(s):
    lines=["# 過去のブラックフライデー資料：観測値と買い時の目安","",
      f'更新：{s["generated_at"]}（JST）',"",
      f'収録キャンペーン記録：{s["campaign_record_count"]}件 / 商品価格記録：{s["historical_deal_record_count"]}件',
      f'対象年：{", ".join(map(str,s["campaign_years_covered"]))}',"",
      "## ここから読み取れること","",
      "- Amazonの本セールは2023〜2025年の記録では、いずれも11月末〜12月初めに8日間実施。先行セールの日数・開始日は年によって違うため、2026年の開催日を過去の曜日だけで決めない。",
      "- PC専門店のキャンペーンは、オンラインと店頭で期間が違う例がある。PC工房は店頭日替わり特価を実施した実績もあるため、店頭4カテゴリは店舗の在庫・価格を別途確認する。",
      "- 2025年のRTX 5070搭載BTOには¥249,800の例があるが、RAM 16GBのため今回の32GB条件を満たさない。32GB/1TBのRTX 5070 BTOで¥267,800という二次報道もあるが、自作パーツ合計や2026年の実売価格として扱わない。",
      "- 2024年のMSI PRO MP2412は¥9,980、メーカー公称価格目安¥14,800という記録（約32.6%差）。別モデルの値引き率を今回のAOC WQHDモデルにそのまま当てはめない。",
      "- Lenovoの2024年公式セール例ではモニター約11〜33%引き、マウス約27%引きの個別事例がある。ただし製品クラス・販売チャネルが異なるため、今回の特定型番の値下げ確率ではない。","",
      "## 商品カテゴリごとの収録状況","",
      "|カテゴリ|記録件数|販売価格レンジ|値引き率付き事例|同一条件の典型値|",
      "|---|---:|---:|---:|---|"]
    for cat,b in sorted(s["categories"].items()):
        rng=b["sale_price_range_jpy"]
        lines.append(f'|{cat}|{b["records"]}|¥{rng["min"]:,}〜¥{rng["max"]:,}|{len(b["discount_examples"])}|'+(f'{b["comparable_discount_median_pct"]}%（n={b["comparable_discount_sample_count"]}）' if b["comparable_discount_median_pct"] is not None else "算出不可（同一条件n不足）")+'|')
    lines += ["","## 値引きの確認できた具体例","",
      "|年|販売元|商品|参考価格|観測セール価格|差率|根拠|注意事項|",
      "|---:|---|---|---:|---:|---:|---|---|"]
    examples=[]
    for cat,b in s["categories"].items():
        examples.extend(b["discount_examples"])
    examples.sort(key=lambda r:(r["year"],r["retailer"],r["product"]))
    for d in examples:
        lines.append(f'|{d["year"]}|{d["retailer"]}|{d["product"]}|¥{d["reference_price_jpy"]:,}|¥{d["sale_price_jpy"]:,}|{d["discount_pct"]}%|[{d["source_grade"]}]({d["source_url"]})|{d["notes"]}|')
    lines += ["","## セール価格の全観測一覧（参考情報）","",
      "通常価格を確認できないものも含め、公開記事で確認できた価格全体を掲載する。空欄を0円や値引きなしと解釈せず、通常価格不明の価格から値引き率は計算しない。","",
      "|日付|販売チャネル|販売元|カテゴリ|商品・構成|セール観測価格|比較参考価格|確認できた差率|構成情報|根拠|注意事項|",
      "|---|---|---|---|---|---:|---:|---:|---|---|---|"]
    for d in s["price_observations"]:
        spec=[]
        if d.get("cpu"): spec.append(str(d["cpu"]))
        if d.get("gpu"): spec.append(str(d["gpu"]))
        if d.get("ram_gb") is not None: spec.append(f'{d["ram_gb"]}GB RAM')
        if d.get("ssd_gb") is not None: spec.append(f'{d["ssd_gb"]}GB SSD')
        reference = f'¥{d["reference_price_jpy"]:,}' if d.get("reference_price_jpy") is not None else "不明"
        pct = f'{d["discount_pct"]}%' if d.get("discount_pct") is not None else "算出不可"
        lines.append(f'|{d["event_date"]}|{d["channel"]}|{d["retailer"]}|{d["category"]}|{d["product"]}|¥{d["sale_price_jpy"]:,}|{reference}|{pct}|{", ".join(spec) if spec else "未確認"}|[{d["source_grade"]}]({d["source_url"]})|{d["notes"]}|')
    lines += ["","## 集計上の制限","",
      "- この表は公開記事・公式告知で見つかった観測値の集合で、各店・各日の全価格履歴ではない。",
      "- 商品が違う、構成が違う、通常価格が独立検証されていない、ポイントが現金値引きではない等の場合は、単純な平均値を「通常の値下げ幅」として出さない。",
      "- 過去の最低価格に合わせることを2026年の目標や予測にせず、今年の同一SKUについて、セール前の直接価格、価格履歴、現在の在庫、完成構成・店頭価格を別に比較する。",
      "- 2026年公式日程が見つかるまでは、観測日をBF実売と認定しない。",
      "","## 収録した公式・報道ソース一覧",""]
    for c in s["retailer_year_channel_records"].items():
        key, arr=c
        for r in arr:
            lines.append(f'- {key} / {r["channel"]}: {r.get("start_jst") or "開始日未確定"}〜{r.get("end_jst") or "終了日未確定"} ({r["source_grade"]}) [{r["source_url"]}]({r["source_url"]})')
    return "\n".join(lines)+"\n"

def main():
    campaigns, deals=load_records()
    analysis=summarize(campaigns, deals)
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_JSON,"w",encoding="utf-8") as f: json.dump(analysis,f,ensure_ascii=False,indent=2); f.write("\n")
    with open(OUT_MD,"w",encoding="utf-8") as f: f.write(render_md(analysis))
    print(f'HISTORICAL_BF_OK campaigns={analysis["campaign_record_count"]} deals={analysis["historical_deal_record_count"]} categories={len(analysis["categories"])}')
    print(f'REPORT={OUT_MD}')
    return analysis

if __name__=="__main__":
    main()
