import json
import os
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def parse_dt(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JST)
        return dt.astimezone(JST)
    except Exception:
        return None

def configured_watch_window(now, config):
    """Return True/False from config's provisional watch window, or None if invalid.

    This is only an observation-cadence window; it never confirms a retailer sale.
    """
    if not isinstance(config, dict):
        return None
    start = parse_dt(config.get("monitor_window_start"))
    end = parse_dt(config.get("monitor_window_end"))
    if start is None or end is None or end < start:
        return None
    if now.tzinfo is None:
        now = now.replace(tzinfo=JST)
    return start <= now.astimezone(JST) <= end

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
    config_path = os.path.join(ROOT, "config", "targets.json")
    try:
        monitor_config = read_json(config_path)
        provisional_window_active = configured_watch_window(now, monitor_config)
    except Exception:
        monitor_config = {}
        provisional_window_active = None
    if provisional_window_active is None:
        # Unknown configuration must not relax freshness checks.
        problems.append("monitor_window_config_missing_or_invalid")
        strict_freshness = True
    else:
        strict_freshness = provisional_window_active
    threshold = timedelta(minutes=20 if strict_freshness else 45)

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
        peripheral_threshold = timedelta(minutes=20 if strict_freshness else 45)
        if peripheral_generated is None:
            problems.append("peripheral_prices_generated_at_missing")
        elif now - peripheral_generated > peripheral_threshold:
            problems.append(f"peripheral_prices_stale:{int((now-peripheral_generated).total_seconds()/60)}m")
    except Exception as exc:
        problems.append("peripheral_prices_unreadable:" + type(exc).__name__)

    result = {
        "status": "PASS" if not problems else "ALERT",
        "checked_at": now.isoformat(),
        "provisional_watch_window_active": provisional_window_active,
        "monitor_window_type": monitor_config.get("monitor_window_type") if isinstance(monitor_config, dict) else None,
        "monitor_window_config_valid": provisional_window_active is not None,
        "problems": problems,
    }
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(1 if problems else 0)

if __name__ == "__main__":
    main()
