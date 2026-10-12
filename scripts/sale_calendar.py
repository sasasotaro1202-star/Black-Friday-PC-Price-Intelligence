"""Retailer-specific, source-verified 2026 campaign calendar.

The broad observation window is only a monitoring guardrail. A timestamp inside
that window does not prove a retailer has started its official Black Friday
campaign. Purchase authorization requires an explicit 2026 date range from an
official retailer source.
"""
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

JST = timezone(timedelta(hours=9))
CONFIRMED_STATUSES = {"CONFIRMED", "CONFIRMED_MANUAL"}


def parse_calendar_dt(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt.astimezone(JST)


def retailer_key_for_url(url):
    """Map a real retailer-hosted product URL to a configured official calendar."""
    try:
        host = (urlparse(str(url or "")).hostname or "").lower()
    except Exception:
        return None
    if not host:
        return None
    domains = [
        ("amazon_japan", ("amazon.co.jp",)),
        ("lenovo", ("lenovo.com",)),
        ("asus", ("asus.com",)),
        ("mouse_computer", ("mouse-jp.co.jp", "mouse-computer.co.jp")),
        ("dospara", ("dospara.co.jp",)),
        ("acer", ("acer.com",)),
        ("frontier", ("frontier-direct.jp", "frontier-k.co.jp")),
        ("ark", ("ark-pc.co.jp",)),
        ("tsukumo", ("tsukumo.co.jp",)),
        ("sycom", ("sycom.co.jp",)),
        ("storm", ("stormst.com", "storm.co.jp")),
        ("yodobashi", ("yodobashi.com",)),
        ("bic_camera", ("biccamera.com",)),
        ("edifier", ("edifier.jp",)),
        ("askul", ("askul.co.jp",)),
    ]
    for key, suffixes in domains:
        if any(host == suffix or host.endswith("." + suffix) for suffix in suffixes):
            return key
    return None


def campaign_entry_for_retailer(retailer_key, config=None, status_data=None):
    """Return only a confirmed calendar entry; unknown/unconfirmed is fail-closed."""
    if not retailer_key:
        return {"status": "UNCONFIRMED", "start_jst": None, "end_jst": None, "source_url": None}
    configured = (config or {}).get("official_2026_dates") or {}
    manual = configured.get(retailer_key) or {}
    discovered = ((status_data or {}).get("sources") or {}).get(retailer_key) or {}
    # A machine-discovered official source range takes precedence only when it
    # passed explicit-year checks. Otherwise a manually documented confirmed
    # entry may be used; unconfirmed scraper output never overrides it.
    candidates = [discovered, manual]
    for entry in candidates:
        start = parse_calendar_dt(entry.get("start_jst") or entry.get("start"))
        end = parse_calendar_dt(entry.get("end_jst") or entry.get("end"))
        status = str(entry.get("status") or "UNCONFIRMED").upper()
        source_url = str(entry.get("source_url") or "")
        if status in CONFIRMED_STATUSES and start and end and start <= end and source_url.startswith("https://"):
            return {
                "status": "CONFIRMED",
                "start_jst": start.isoformat(),
                "end_jst": end.isoformat(),
                "source_url": source_url,
                "evidence": entry.get("evidence"),
                "checked_at": entry.get("checked_at"),
            }
    if discovered:
        return {
            "status": str(discovered.get("status") or "UNCONFIRMED").upper(),
            "start_jst": discovered.get("start_jst"),
            "end_jst": discovered.get("end_jst"),
            "source_url": discovered.get("source_url"),
            "evidence": discovered.get("evidence"),
            "checked_at": discovered.get("checked_at"),
        }
    return {
        "status": str(manual.get("status") or "UNCONFIRMED").upper(),
        "start_jst": manual.get("start_jst") or manual.get("start"),
        "end_jst": manual.get("end_jst") or manual.get("end"),
        "source_url": manual.get("source_url"),
        "evidence": manual.get("evidence"),
        "checked_at": manual.get("checked_at"),
    }


def campaign_window_for_item(item, now, config=None, status_data=None):
    """Identify whether this product's seller has a confirmed active 2026 sale."""
    url = (item or {}).get("purchase_url") or (item or {}).get("url")
    retailer_key = retailer_key_for_url(url)
    entry = campaign_entry_for_retailer(retailer_key, config, status_data)
    start = parse_calendar_dt(entry.get("start_jst"))
    end = parse_calendar_dt(entry.get("end_jst"))
    now_dt = parse_calendar_dt(now)
    observed = parse_calendar_dt((item or {}).get("retrieval_time"))
    date_confirmed = entry.get("status") in CONFIRMED_STATUSES and start is not None and end is not None
    active_now = bool(date_confirmed and now_dt and start <= now_dt <= end)
    active_at_observation = bool(
        active_now and observed and start <= observed <= end
    )
    return {
        "retailer_key": retailer_key,
        "status": "CONFIRMED_ACTIVE" if active_at_observation else (
            "CONFIRMED_NOT_ACTIVE" if date_confirmed else "UNCONFIRMED"
        ),
        "date_status": entry.get("status", "UNCONFIRMED"),
        "start_jst": start.isoformat() if start else None,
        "end_jst": end.isoformat() if end else None,
        "source_url": entry.get("source_url"),
        "active_now": active_now,
        "active_at_observation": active_at_observation,
        "evidence": entry.get("evidence"),
    }
