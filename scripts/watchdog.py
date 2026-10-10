import json
import os
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def parse_dt(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(JST)
    except Exception:
        return None

def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def main():
    now = datetime.now(JST)
    latest_path = os.path.join(ROOT, "data", "current_latest.json")
    ranking_path = os.path.join(ROOT, "data", "decision_rankings.json")
    peripheral_path = os.path.join(ROOT, "data", "peripheral_prices.json")
    problems = []

    try:
        latest = read_json(latest_path)
    except Exception as exc:
        latest = {}
        problems.append("current_latest_unreadable:" + type(exc).__name__)

    generated = parse_dt(latest.get("generated_at"))
    start = datetime(2026, 11, 14, tzinfo=JST)
    end = datetime(2026, 12, 4, 23, 59, 59, tzinfo=JST)
    in_bf = start <= now <= end
    threshold = timedelta(minutes=20 if in_bf else 45)

    if generated is None:
        problems.append("latest_generated_at_missing")
    elif now - generated > threshold:
        problems.append(f"latest_data_stale:{int((now-generated).total_seconds()/60)}m")

    try:
        ranking = read_json(ranking_path)
    except Exception as exc:
        ranking = {}
        problems.append("rankings_unreadable:" + type(exc).__name__)

    ranking_generated = parse_dt(ranking.get("generated_at"))
    if generated and ranking_generated:
        if ranking_generated < generated - timedelta(minutes=20):
            problems.append("ranking_stale_relative_to_latest")

    try:
        peripherals = read_json(peripheral_path)
        peripheral_generated = parse_dt(peripherals.get("generated_at"))
        peripheral_threshold = timedelta(minutes=20 if in_bf else 45)
        if peripheral_generated is None:
            problems.append("peripheral_prices_generated_at_missing")
        elif now - peripheral_generated > peripheral_threshold:
            problems.append(f"peripheral_prices_stale:{int((now-peripheral_generated).total_seconds()/60)}m")
    except Exception as exc:
        problems.append("peripheral_prices_unreadable:" + type(exc).__name__)

    result = {
        "status": "PASS" if not problems else "ALERT",
        "checked_at": now.isoformat(),
        "black_friday_window": in_bf,
        "problems": problems,
    }
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(1 if problems else 0)

if __name__ == "__main__":
    main()
