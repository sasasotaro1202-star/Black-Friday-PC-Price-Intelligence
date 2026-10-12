"""Fetch retailer-owned pages and recognize only explicit 2026 Black Friday date ranges.

No date is inferred from last year's dates, weekday alignment, generic sale text,
or yearless MM/DD ranges. Network/parse failures remain unconfirmed.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JST = timezone(timedelta(hours=9))
OUTPUT = os.path.join(ROOT, "data", "official_campaign_dates_status.json")
CACHE_HOURS = 6
DATE_RANGE = re.compile(
    r"(?P<year>2026)\s*(?:年|[./-])\s*(?P<month>\d{1,2})\s*(?:月|[./-])\s*(?P<day>\d{1,2})\s*日?"
    r"\s*(?:\([^)]{0,30}\))?\s*(?:(?P<start_hour>\d{1,2}):(?P<start_minute>\d{2}))?\s*"
    r"(?:～|〜|~|–|—|－|-|から|to|through)\s*"
    r"(?:(?P<end_year>2026)\s*(?:年|[./-])\s*)?"
    r"(?P<end_month>\d{1,2})\s*(?:月|[./-])\s*(?P<end_day>\d{1,2})\s*日?"
    r"\s*(?:\([^)]{0,30}\))?\s*(?:(?P<end_hour>\d{1,2}):(?P<end_minute>\d{2}))?",
    re.IGNORECASE,
)
BF_WORDS = re.compile(r"ブラック\s*フライデー|black\s*friday|pre[- ]?black\s*friday", re.IGNORECASE)


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.links = []
        self.skip = 0
        self.active_href = None
        self.active_link_text = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1
        if tag == "a" and not self.skip:
            self.active_href = dict(attrs).get("href")
            self.active_link_text = []

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "a" and self.active_href:
            self.links.append({"href": self.active_href, "text": " ".join(self.active_link_text).strip()})
            self.active_href = None
            self.active_link_text = []
        if tag in ("script", "style", "noscript", "svg") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data and data.strip():
            self.parts.append(data.strip())
            if self.active_href:
                self.active_link_text.append(data.strip())


def now_jst():
    return datetime.now(JST)


def iso(dt):
    return dt.astimezone(JST).isoformat()


def parse_dt(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt.astimezone(JST)


def visible_text_and_links(payload):
    parser = VisibleText()
    parser.feed(payload.decode("utf-8", errors="replace"))
    text = re.sub(r"\s+", " ", " ".join(parser.parts))
    return text, parser.links


def visible_text(payload):
    return visible_text_and_links(payload)[0]


def parse_explicit_2026_range(text, source_url):
    """Return a dated range only when year 2026 is explicit at the start."""
    text = re.sub(r"\s+", " ", str(text or "")).replace("（", "(").replace("）", ")")
    lowered_url = str(source_url or "").lower()
    dedicated_url = "black-friday" in lowered_url or "blackfriday" in lowered_url or "pre-blackfriday" in lowered_url
    for match in DATE_RANGE.finditer(text):
        left = max(0, match.start() - 180)
        right = min(len(text), match.end() + 180)
        context = text[left:right]
        if not dedicated_url and not BF_WORDS.search(context):
            continue
        try:
            start = datetime(
                2026,
                int(match.group("month")),
                int(match.group("day")),
                int(match.group("start_hour") or 0),
                int(match.group("start_minute") or 0),
                tzinfo=JST,
            )
            end_year = int(match.group("end_year") or 2026)
            end = datetime(
                end_year,
                int(match.group("end_month")),
                int(match.group("end_day")),
                int(match.group("end_hour") or 23),
                int(match.group("end_minute") or 59),
                59,
                tzinfo=JST,
            )
        except (TypeError, ValueError):
            continue
        # Restrict detected ranges to the late-year campaign context and disallow
        # overnight/reversed date mistakes or dates copied from unrelated content.
        if start.year != 2026 or end.year != 2026 or start.month < 10 or end.month > 12:
            continue
        if end < start or (end - start).days > 60:
            continue
        snippet = text[max(0, match.start() - 90):min(len(text), match.end() + 90)]
        return {
            "start_jst": start.isoformat(),
            "end_jst": end.isoformat(),
            "evidence": snippet,
        }
    return None


def fetch_page(url, timeout=8):
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; BFPriceIntelligence/1.0; +https://github.com/sasasotaro1202-star/Black-Friday-PC-Price-Intelligence)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        if response.status < 200 or response.status >= 300:
            raise RuntimeError("HTTP status {}".format(response.status))
        final_url = response.geturl() or url
        return visible_text_and_links(response.read()), final_url


def _same_official_site(seed_url, candidate_url):
    try:
        base = (urlparse(seed_url).hostname or "").lower()
        host = (urlparse(candidate_url).hostname or "").lower()
        # Normalize only a leading www.; never treat a shared public suffix
        # such as co.jp as evidence that two unrelated domains are the same site.
        base = base[4:] if base.startswith("www.") else base
        host = host[4:] if host.startswith("www.") else host
        return bool(
            urlparse(candidate_url).scheme == "https"
            and base and host
            and (host == base or host.endswith("." + base))
        )
    except Exception:
        return False


def discover_campaign_links(seed_url, links, already_checked, limit=4):
    """Return a few likely campaign links that stay on the same retailer domain."""
    candidates = []
    seen = set(already_checked or [])
    for link in links or []:
        href = link.get("href") if isinstance(link, dict) else None
        label = str(link.get("text") or "") if isinstance(link, dict) else ""
        if not href:
            continue
        absolute = urljoin(seed_url, href).split("#", 1)[0]
        parsed = urlparse(absolute)
        if not _same_official_site(seed_url, absolute) or parsed.path.lower().endswith((".pdf", ".jpg", ".png", ".webp", ".jpeg")):
            continue
        if absolute in seen or absolute in {x.rstrip("/") for x in seen}:
            continue
        target = (absolute + " " + label).lower()
        # A link must be clearly campaign-oriented; do not crawl a whole catalog.
        if not re.search(r"black[-_ ]?friday|blackfriday|ブラック\s*フライデー|campaign|campaigns|sale|セール|特集", target, re.IGNORECASE):
            continue
        candidates.append((absolute, label))
    # Prefer strongly named Black Friday destinations over generic campaign hubs.
    candidates.sort(key=lambda x: (
        0 if re.search(r"black[-_ ]?friday|blackfriday|ブラック\s*フライデー", x[0] + " " + x[1], re.IGNORECASE) else 1,
        x[0],
    ))
    return [url for url, _ in candidates[:max(0, int(limit))]]


def load_json(path, fallback):
    try:
        with open(path, encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, ValueError, TypeError):
        return fallback


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    os.replace(temporary, path)


def calendar_config_signature(calendar):
    """Stable signature that invalidates cached status when retailers or URLs change."""
    result = {}
    for key, configured in (calendar or {}).items():
        if key == "note" or not isinstance(configured, dict):
            continue
        urls = configured.get("source_urls") or ([configured.get("source_url")] if configured.get("source_url") else [])
        result[str(key)] = sorted(set(
            url.strip() for url in urls
            if isinstance(url, str) and url.strip().startswith("https://")
        ))
    return dict(sorted(result.items()))


def should_skip_calendar_refresh(old, calendar, now, cache_hours=CACHE_HOURS):
    old_checked = parse_dt((old or {}).get("checked_at"))
    old_sources = (old or {}).get("sources") or {}
    expected_signature = calendar_config_signature(calendar)
    if not old_checked or now - old_checked >= timedelta(hours=cache_hours):
        return False
    if (old or {}).get("configured_sources") != expected_signature:
        return False
    return set(old_sources) == set(expected_signature)


def main():
    config = load_json(os.path.join(ROOT, "config", "targets.json"), {})
    calendar = config.get("official_2026_dates") or {}
    old = load_json(OUTPUT, {})
    now = now_jst()
    old_sources = old.get("sources") or {}
    signature = calendar_config_signature(calendar)
    if should_skip_calendar_refresh(old, calendar, now):
        print("Official campaign calendar check skipped: matching configuration cache is fresh.")
        return 0

    output = {
        "generated_at": iso(now),
        "checked_at": iso(now),
        "configured_sources": signature,
        "policy": "Only official retailer sources with an explicit 2026 date range can set CONFIRMED. Provisional watch-window dates never confirm a retailer campaign.",
        "sources": {},
    }

    for key, configured in calendar.items():
        if key == "note" or not isinstance(configured, dict):
            continue
        urls = configured.get("source_urls") or ([configured.get("source_url")] if configured.get("source_url") else [])
        urls = [u for u in urls if isinstance(u, str) and u.startswith("https://")]
        previous = old_sources.get(key) or {}
        confirmed = None
        checked_sources = []
        errors = []
        visited = set()
        for seed_url in urls:
            if confirmed or len(visited) >= 3:
                break
            queue = [(seed_url, None)]
            while queue and len(visited) < 3 and not confirmed:
                url, discovered_from = queue.pop(0)
                if url in visited:
                    continue
                visited.add(url)
                try:
                    (page_text, links), final_url = fetch_page(url)
                    if not _same_official_site(seed_url, final_url):
                        checked_sources.append({
                            "url": url, "final_url": final_url, "fetch_status": "REJECTED_CROSS_DOMAIN_REDIRECT",
                            "explicit_2026_range_found": False,
                        })
                        continue
                    parsed = parse_explicit_2026_range(page_text, final_url)
                    checked_sources.append({
                        "url": final_url, "discovered_from": discovered_from,
                        "fetch_status": "OK", "explicit_2026_range_found": bool(parsed),
                    })
                    if parsed:
                        confirmed = dict(
                            parsed, source_url=final_url, status="CONFIRMED",
                            checked_at=iso(now), fetch_status="OK",
                            discovered_from=discovered_from,
                        )
                        break
                    if len(visited) < 3:
                        discovered = discover_campaign_links(
                            final_url, links, visited, limit=4
                        )
                        for child in discovered:
                            if child not in visited and all(item[0] != child for item in queue):
                                queue.append((child, final_url))
                except (HTTPError, URLError, TimeoutError, OSError, RuntimeError, ValueError) as error:
                    errors.append("{}: {}".format(url, str(error)[:240]))
                    checked_sources.append({
                        "url": url, "discovered_from": discovered_from,
                        "fetch_status": "ERROR", "error": str(error)[:240],
                    })

        if confirmed:
            entry = confirmed
        elif previous.get("status") == "CONFIRMED" and previous.get("start_jst") and previous.get("end_jst"):
            # Preserve a previously source-verified calendar range if a later fetch
            # is blocked or the landing page rotates to a new page after announcing it.
            entry = dict(previous)
            entry["checked_at"] = iso(now)
            entry["latest_fetch_status"] = "ERROR" if errors else "NO_NEW_2026_RANGE"
            entry["last_check_errors"] = errors
        elif errors and not any(x.get("fetch_status") == "OK" for x in checked_sources):
            entry = {
                "status": "FETCH_ERROR",
                "start_jst": None,
                "end_jst": None,
                "source_url": urls[0] if urls else None,
                "evidence": None,
                "checked_at": iso(now),
                "latest_fetch_status": "ERROR",
                "last_check_errors": errors,
            }
        else:
            entry = {
                "status": "UNCONFIRMED",
                "start_jst": None,
                "end_jst": None,
                "source_url": next((x["url"] for x in checked_sources if x.get("fetch_status") == "OK"), urls[0] if urls else None),
                "evidence": None,
                "checked_at": iso(now),
                "latest_fetch_status": "NO_EXPLICIT_2026_RANGE",
                "last_check_errors": errors,
            }
        entry["sources_checked"] = checked_sources
        output["sources"][key] = entry

    entries = list(output["sources"].values())
    output["summary"] = {
        "retailer_count": len(entries),
        "confirmed_count": sum(1 for entry in entries if entry.get("status") == "CONFIRMED"),
        "unconfirmed_count": sum(1 for entry in entries if entry.get("status") == "UNCONFIRMED"),
        "fetch_error_count": sum(1 for entry in entries if entry.get("status") == "FETCH_ERROR"),
    }
    save_json(OUTPUT, output)
    print(json.dumps(output["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
