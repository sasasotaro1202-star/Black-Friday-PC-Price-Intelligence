#!/usr/bin/env python3
"""Report whether data/watchlist.json needs refreshing.

This is called *after* a workflow resets to origin/main, so discovery decisions
are based on the exact watchlist that will be used by this collection attempt.
Output is exactly "true" or "false" for robust shell use.
"""
import json
import os
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCHLIST_PATH = os.path.join(ROOT, "data", "watchlist.json")
MAX_AGE_SECONDS = 24 * 60 * 60


def needs_refresh(path=WATCHLIST_PATH, now=None):
    now = now or datetime.now(JST)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        urls = data.get("urls") or []
        raw_generated = data.get("generated_at")
        if not urls or not raw_generated:
            return True
        generated = datetime.fromisoformat(str(raw_generated).replace("Z", "+00:00"))
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=JST)
        age_seconds = (
            now.astimezone(timezone.utc) - generated.astimezone(timezone.utc)
        ).total_seconds()
        return age_seconds < 0 or age_seconds >= MAX_AGE_SECONDS
    except Exception:
        return True


def main():
    print("true" if needs_refresh() else "false")


if __name__ == "__main__":
    main()
