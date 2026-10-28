import json
import os
import re
import subprocess
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



def latest_input_change_at(root=ROOT):
    """Return the newest commit timestamp touching runtime inputs.

    Data-only commits must not advance this timestamp; source/config/workflow
    changes must be followed by a newly collected snapshot. Full git history is
    required by the watchdog workflow so shallow clones do not silently skip it.
    """
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", "scripts", "config", ".github/workflows"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return parse_dt(result.stdout.strip())


def snapshot_predates_inputs(snapshot_generated_at, latest_input_changed_at):
    """True when source/config inputs changed after the data snapshot was built."""
    snapshot_time = parse_dt(snapshot_generated_at)
    input_change_time = parse_dt(latest_input_changed_at)
    return bool(
        snapshot_time is not None
        and input_change_time is not None
        and input_change_time > snapshot_time
    )



def self_build_artifact_problems(root, now, threshold):
    """Validate freshness and core invariants of the self-build data path."""
    problems = []
    data_dir = os.path.join(root, "data")
    config_dir = os.path.join(root, "config")

    component_prices = {}
    component_generated = None
    try:
        component_prices = read_json(os.path.join(data_dir, "build_component_prices.json"))
        component_generated = parse_dt(component_prices.get("generated_at"))
        if component_generated is None:
            problems.append("build_component_prices_generated_at_missing")
        elif now.astimezone(JST) - component_generated > threshold:
            problems.append("build_component_prices_stale")
    except Exception as exc:
        problems.append("build_component_prices_unreadable:" + type(exc).__name__)

    plan = {}
    plan_generated = None
    try:
        plan = read_json(os.path.join(data_dir, "self_build_plan.json"))
        plan_generated = parse_dt(plan.get("generated_at"))
        if plan_generated is None:
            problems.append("self_build_plan_generated_at_missing")
        elif now.astimezone(JST) - plan_generated > threshold:
            problems.append("self_build_plan_stale")
    except Exception as exc:
        problems.append("self_build_plan_unreadable:" + type(exc).__name__)

    if component_generated is not None and plan_generated is not None:
        if plan_generated < component_generated - timedelta(minutes=5):
            problems.append("self_build_plan_stale_relative_to_component_prices")

    try:
        build_config = read_json(os.path.join(config_dir, "build_components.json"))
    except Exception as exc:
        build_config = {}
        problems.append("build_components_config_unreadable:" + type(exc).__name__)
    try:
        targets_config = read_json(os.path.join(config_dir, "targets.json"))
    except Exception as exc:
        targets_config = {}
        problems.append("targets_config_unreadable:" + type(exc).__name__)

    if plan and targets_config:
        total = plan.get("total_budget_jpy")
        soft_total = plan.get("soft_ceiling_total_jpy", total)
        pc_budget = plan.get("pc_budget_jpy")
        pc_planned = plan.get("pc_planned_budget_jpy")
        peripheral = plan.get("peripheral_budget_jpy")
        contingency = plan.get("unallocated_contingency_jpy")
        if total != targets_config.get("total_budget_jpy"):
            problems.append("self_build_total_budget_differs_from_target_config")
        if peripheral != targets_config.get("peripheral_budget_jpy"):
            problems.append("self_build_peripheral_budget_differs_from_target_config")
        expected_soft_total = targets_config.get("soft_ceiling_total_jpy", total)
        if soft_total != expected_soft_total:
            problems.append("self_build_soft_ceiling_differs_from_target_config")
        # pc_planned_budget_jpy is the planning allowance inside the soft ceiling,
        # not the strict target total. The 40k comparison band permits a 380k PC
        # plan plus 35k peripherals and 5k contingency = 420k, while retaining
        # 400k as the preferred target for the complete system.
        if all(isinstance(x, int) and not isinstance(x, bool)
               for x in (total, soft_total, pc_budget, pc_planned, peripheral, contingency)):
            expected_pc_planned = max(0, min(pc_budget, soft_total - peripheral - contingency))
            if pc_planned != expected_pc_planned:
                problems.append("self_build_dynamic_pc_budget_mismatch")
            if pc_planned + peripheral + contingency != soft_total:
                problems.append("self_build_all_in_budget_arithmetic_mismatch")
        else:
            problems.append("self_build_budget_fields_missing_or_invalid")
        if plan.get("budget_arithmetic_valid") is not True:
            problems.append("self_build_budget_arithmetic_invalid")

    builds = plan.get("builds") or []
    total_budget = plan.get("total_budget_jpy")
    if not isinstance(builds, list) or len(builds) != 3:
        problems.append("self_build_ranked_gpu_build_count_invalid")
        builds = []
    if isinstance(total_budget, int) and builds:
        target_fits = [
            item for item in builds
            if isinstance(item, dict)
            and isinstance(item.get("target_all_in_jpy"), int)
            and item["target_all_in_jpy"] <= total_budget
        ]
        if not target_fits:
            problems.append("no_self_build_target_fits_total_budget")

        for item in builds:
            if not isinstance(item, dict):
                continue
            pc_total = item.get("target_pc_total_jpy")
            all_in = item.get("target_all_in_jpy")
            if (isinstance(pc_total, int) and isinstance(all_in, int)
                    and isinstance(peripheral, int) and isinstance(contingency, int)):
                if all_in != pc_total + peripheral + contingency:
                    problems.append("self_build_candidate_all_in_arithmetic_mismatch:" + str(item.get("id") or item.get("gpu_choice_id") or "unknown"))

    profile = build_config.get("profile") or {}
    primary_memory_id = str(profile.get("primary_memory_choice_id") or "")
    parts_by_id = {
        str(item.get("id")): item
        for item in (build_config.get("parts") or [])
        if isinstance(item, dict) and item.get("id")
    }
    primary_memory = parts_by_id.get(primary_memory_id) or {}
    primary_capacity = (primary_memory.get("specs") or {}).get("capacity_gb")
    if primary_capacity is not None and builds:
        for item in builds:
            if not isinstance(item, dict):
                continue
            selected_id = str(item.get("selected_memory_id") or "")
            selected = parts_by_id.get(selected_id) or {}
            selected_capacity = (selected.get("specs") or {}).get("capacity_gb")
            if selected_capacity is not None and selected_capacity != primary_capacity:
                problems.append("self_build_base_memory_capacity_mismatch:" + str(item.get("id") or selected_id))

    # Both reports are derived from the build plan; detect if either one is old.
    for relative_path, label in (
        ("reports/latest.md", "latest_report"),
        ("reports/self-build-ranking.md", "self_build_report"),
    ):
        path = os.path.join(data_dir, relative_path)
        try:
            with open(path, encoding="utf-8") as stream:
                report_text = stream.read()
            match = re.search(r"^更新:\s*(.+?)\s*$", report_text, re.M)
            report_generated = parse_dt(match.group(1)) if match else None
            if report_generated is None:
                problems.append(label + "_generated_at_missing")
            else:
                if now.astimezone(JST) - report_generated > threshold:
                    problems.append(label + "_stale")
                if plan_generated is not None and abs(report_generated - plan_generated) > timedelta(minutes=10):
                    problems.append(label + "_stale_relative_to_self_build_plan")
        except Exception as exc:
            problems.append(label + "_unreadable:" + type(exc).__name__)

    return problems

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
    latest_input_changed_at = latest_input_change_at(ROOT)
    if latest_input_changed_at is None:
        problems.append("input_change_timestamp_unavailable")
    elif snapshot_predates_inputs(latest.get("generated_at"), latest_input_changed_at.isoformat()):
        problems.append("latest_data_predates_code_or_config_change")

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

    problems.extend(self_build_artifact_problems(ROOT, now, threshold))

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
