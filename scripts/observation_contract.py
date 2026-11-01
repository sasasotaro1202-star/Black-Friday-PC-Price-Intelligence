"""Fail-closed schema checks for primary price-observation metadata.

These checks do not claim that an external store is healthy or that a price is
buyable. They ensure the monitor cannot report a healthy pipeline when the
coverage/fetch counters needed to evaluate that pipeline have disappeared.
"""

import math
from datetime import datetime


_COVERAGE_INTEGER_FIELDS = (
    "watchlist_count",
    "processed_count",
    "skipped_count",
    "max_urls",
)
_COVERAGE_RATE_FIELDS = (
    "processing_rate_pct",
    "transport_success_rate_pct",
    "price_verified_rate_pct",
)
_FETCH_COUNTER_FIELDS = (
    "total",
    "direct_verified",
    "search_corrob",
    "stale_previous",
    "baseline_only",
    "anomaly_rejected",
    "errors",
)


def observation_metadata_schema_errors(snapshot):
    """Return schema errors for required monitoring-coverage and fetch counters."""
    errors = []
    if not isinstance(snapshot, dict):
        return ["snapshot is not an object"]

    products = snapshot.get("products")
    if not isinstance(products, list):
        errors.append("products is missing or is not a list")
        product_count = None
    else:
        product_count = len(products)

    coverage = snapshot.get("coverage")
    if not isinstance(coverage, dict) or not coverage:
        errors.append("coverage is missing or is not an object")
    else:
        for field in _COVERAGE_INTEGER_FIELDS:
            value = coverage.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                errors.append(f"coverage.{field} is missing or invalid")
        for field in _COVERAGE_RATE_FIELDS:
            value = coverage.get(field)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0 <= value <= 100
            ):
                errors.append(f"coverage.{field} is missing or invalid")

        skipped_ids = coverage.get("skipped_ids")
        if not isinstance(skipped_ids, list) or any(
            not isinstance(item, str) or not item for item in skipped_ids
        ):
            errors.append("coverage.skipped_ids is missing or invalid")
        elif len(skipped_ids) != len(set(skipped_ids)):
            errors.append("coverage.skipped_ids contains duplicates")

    fetch_stats = snapshot.get("fetch_stats")
    if not isinstance(fetch_stats, dict) or not fetch_stats:
        errors.append("fetch_stats is missing or is not an object")
    else:
        for field in _FETCH_COUNTER_FIELDS:
            value = fetch_stats.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                errors.append(f"fetch_stats.{field} is missing or invalid")
        total = fetch_stats.get("total")
        if (
            product_count is not None
            and isinstance(total, int)
            and not isinstance(total, bool)
            and total != product_count
        ):
            errors.append("fetch_stats.total does not match products length")

    return errors



def purchase_gate_schema_errors(rankings):
    """Require current purchase-gate fields; legacy ranking snapshots fail closed."""
    errors = []
    if not isinstance(rankings, dict):
        return ["rankings is not an object"]

    quality = rankings.get("quality")
    if not isinstance(quality, dict) or not quality:
        errors.append("rankings.quality is missing or is not an object")
    else:
        for field in ("critical_candidate_count", "critical_unverified_count"):
            value = quality.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                errors.append(f"quality.{field} is missing or invalid")
        if quality.get("coverage_status") not in ("COMPLETE", "PARTIAL"):
            errors.append("quality.coverage_status is missing or invalid")

    gate = rankings.get("purchase_gate")
    if not isinstance(gate, dict) or not gate:
        errors.append("purchase_gate is missing or is not an object")
        return errors

    if not isinstance(gate.get("allowed"), bool):
        errors.append("purchase_gate.allowed is missing or invalid")
    gate_status = gate.get("coverage_status")
    if gate_status not in ("COMPLETE", "PARTIAL"):
        errors.append("purchase_gate.coverage_status is missing or invalid")
    elif isinstance(quality, dict) and quality.get("coverage_status") != gate_status:
        errors.append("purchase_gate.coverage_status does not match quality.coverage_status")

    ids = gate.get("critical_unverified_ids")
    if not isinstance(ids, list) or any(not isinstance(item, str) or not item for item in ids):
        errors.append("purchase_gate.critical_unverified_ids is missing or invalid")
    elif len(ids) != len(set(ids)):
        errors.append("purchase_gate.critical_unverified_ids contains duplicates")

    return errors


_PIT_EVENT_TIMESTAMP_FIELDS = (
    "event_time",
    "publication_time",
    "available_at",
    "retrieval_time",
    "prediction_time",
)


def point_in_time_event_metadata(event):
    """Validate the complete event-time/publication/availability/knowledge chain.

    Missing event or publisher timestamps are common for retail pages. They must
    remain UNKNOWN rather than being filled with the observation time. Only a
    complete, timezone-aware, monotonically ordered chain is PIT-valid.
    """
    if not isinstance(event, dict):
        return {
            "pit_valid": False,
            "pit_status": "INVALID",
            "pit_missing_fields": list(_PIT_EVENT_TIMESTAMP_FIELDS),
            "pit_error": "event_is_not_an_object",
        }

    missing = [
        field for field in _PIT_EVENT_TIMESTAMP_FIELDS
        if event.get(field) in (None, "")
    ]
    parsed = {}
    invalid = []
    for field in _PIT_EVENT_TIMESTAMP_FIELDS:
        value = event.get(field)
        if value in (None, ""):
            continue
        try:
            timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("timezone_offset_missing")
            parsed[field] = timestamp
        except (TypeError, ValueError, OverflowError):
            invalid.append(field)

    if invalid:
        return {
            "pit_valid": False,
            "pit_status": "INVALID",
            "pit_missing_fields": missing,
            "pit_error": "invalid_or_timezone_naive_timestamp:" + ",".join(invalid),
        }
    if missing:
        return {
            "pit_valid": False,
            "pit_status": "UNKNOWN",
            "pit_missing_fields": missing,
            "pit_error": "missing_required_timestamps",
        }

    for earlier, later in zip(_PIT_EVENT_TIMESTAMP_FIELDS, _PIT_EVENT_TIMESTAMP_FIELDS[1:]):
        if parsed[earlier] > parsed[later]:
            return {
                "pit_valid": False,
                "pit_status": "INVALID",
                "pit_missing_fields": [],
                "pit_error": "timestamp_order_violation:" + earlier + ">" + later,
            }

    return {
        "pit_valid": True,
        "pit_status": "VALID",
        "pit_missing_fields": [],
        "pit_error": None,
    }
