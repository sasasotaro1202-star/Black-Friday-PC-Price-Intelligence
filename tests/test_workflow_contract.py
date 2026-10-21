import json
import pathlib
import re
import textwrap
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "pc-price-monitor.yml"


class WorkflowContractTests(unittest.TestCase):
    def test_primary_workflow_skips_unselected_cron_ticks_before_running_tests(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        smoke_at = text.index("Production syntax and fail-closed smoke gate")
        regression_at = text.index("Full regression gate before every production collection")
        gate_at = text.index("Check whether regular monitoring should run")
        monitor_at = text.index("python scripts/monitor.py")
        self.assertLess(smoke_at, regression_at)
        self.assertLess(gate_at, smoke_at)
        self.assertLess(gate_at, monitor_at)
        self.assertIn('python -m unittest discover -s tests -p "test_production_contract.py" -v', text)
        self.assertIn('python -m unittest discover -s tests -p "test_*.py" -v', text)
        self.assertIn("      - name: Production syntax and fail-closed smoke gate\n        if: steps.gate.outputs.skip != 'true'", text)
        self.assertIn("      - name: Full regression gate before every production collection\n        if: steps.gate.outputs.skip != 'true'", text)
        self.assertNotIn("if: github.event_name != 'schedule'", text)

    def test_fast_workflow_has_full_regression_gate_before_monitoring(self):
        path = ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml"
        text = path.read_text(encoding="utf-8")
        gate_at = text.index("Production syntax and regression gate")
        window_at = text.index("Check provisional broad watch window")
        monitor_at = text.index("python scripts/monitor.py")
        self.assertLess(gate_at, window_at)
        self.assertLess(window_at, monitor_at)
        self.assertIn('python -m py_compile scripts/*.py', text)
        self.assertIn('python -m unittest discover -s tests -p "test_*.py" -v', text)

    def test_monitor_cron_has_five_and_fifteen_minute_schedules(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('cron: "3-59/5 * * * *"', text)
        self.assertIn('cron: "7,22,37,52 * * * *"', text)

    def test_schedule_gate_uses_cron_expression_not_runner_start_minute(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("SCHEDULE_CRON: ${{ github.event.schedule }}", text)
        self.assertIn('expected_cron = "3-59/5 * * * *" if in_watch_window else "7,22,37,52 * * * *"', text)
        self.assertIn("run_now = schedule_cron == expected_cron", text)
        self.assertNotIn("regular_due = now.minute % 15 == 0", text)

    def test_campaign_calendar_runs_before_price_strategy_reports(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        calendar_at = text.index("python scripts/official_campaign_dates.py")
        report_at = text.index("python scripts/report.py")
        timing_at = text.index("python scripts/timing_analysis.py")
        self.assertLess(calendar_at, report_at)
        self.assertLess(calendar_at, timing_at)

    def test_timing_report_labels_completed_pc_rows_as_benchmarks_for_self_build(self):
        source = (ROOT / "scripts" / "timing_analysis.py").read_text(encoding="utf-8")
        self.assertIn("Completed-PC / BTO benchmark references (not DIY purchase candidates)", source)
        self.assertIn("completed_pc_benchmark_only_not_actionable", source)
        self.assertIn("must not be used as component prices", source)
        self.assertIn("timing_candidates_section_lines(decision.get(\"purchase_method_policy\"))", source)

    def test_timing_analysis_marks_calendar_date_as_non_authoritative_reference(self):
        source = (ROOT / "scripts" / "timing_analysis.py").read_text(encoding="utf-8")
        self.assertIn("CALENDAR_REFERENCE_DATE", source)
        self.assertIn("calendar_black_friday_reference_date", source)
        self.assertIn("not official retailer sale dates", source)
        self.assertNotIn('"target_black_friday":TARGET.date().isoformat()', source)
        self.assertNotIn('f"Target Black Friday: {TARGET.date()}"', source)

    def test_watch_window_does_not_hardcode_2026_campaign_dates(self):
        paths = (
            WORKFLOW,
            ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml",
            ROOT / "scripts" / "watchdog.py",
        )
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("datetime(2026, 11, 14", text, str(path))
            self.assertNotIn("datetime(2026,11,14", text, str(path))
            self.assertNotIn("datetime(2026, 12, 4", text, str(path))
            self.assertNotIn("datetime(2026,12,4", text, str(path))
        fast = paths[1].read_text(encoding="utf-8")
        watchdog = paths[2].read_text(encoding="utf-8")
        self.assertIn('cfg["monitor_window_start"]', fast)
        self.assertIn('cfg["monitor_window_end"]', fast)
        self.assertIn("monitor_window_start", watchdog)
        self.assertIn("monitor_window_end", watchdog)

    def test_fast_workflow_refreshes_official_dates_before_decision_reports(self):
        text = (ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml").read_text(encoding="utf-8")
        self.assertIn("provisional broad watch window", text)
        self.assertIn("sale_dates_inferred=false", text)
        calendar_at = text.index("python scripts/official_campaign_dates.py")
        report_at = text.index("python scripts/report.py")
        timing_at = text.index("python scripts/timing_analysis.py")
        self.assertLess(calendar_at, report_at)
        self.assertLess(calendar_at, timing_at)

    def test_primary_workflow_runs_peripheral_observer(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python scripts/peripheral_monitor.py", text)

    def test_healthcheck_compares_budget_candidates_to_config_not_fixed_count(self):
        source = (ROOT / "scripts" / "healthcheck.py").read_text(encoding="utf-8")
        self.assertIn('"config", "build_components.json"', source)
        self.assertIn('"budget_build_candidates"', source)
        self.assertIn("budget scenario candidate count does not match config", source)
        self.assertIn("budget scenario candidate IDs do not match config", source)
        self.assertNotIn("len(all_scenario_builds) != 9", source)

    def test_diy_planner_runs_before_derived_timing_and_scenarios(self):
        for path in (
            ROOT / ".github" / "workflows" / "pc-price-monitor.yml",
            ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml",
            ROOT / ".github" / "workflows" / "pc-price-tests.yml",
        ):
            text = path.read_text(encoding="utf-8")
            planner_at = text.index("python scripts/self_build_planner.py")
            timing_at = text.index("python scripts/timing_analysis.py")
            scenario_at = text.index("python scripts/scenario_analysis.py")
            self.assertLess(planner_at, timing_at, str(path))
            self.assertLess(planner_at, scenario_at, str(path))

    def test_fast_workflow_has_no_duplicate_schedule(self):
        text = (ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("  schedule:", text)
        self.assertIn('MONITOR_MAX_URLS: "100"', text)

    def test_embedded_python_blocks_are_syntactically_valid(self):
        for path in (
            ROOT / ".github" / "workflows" / "pc-price-monitor.yml",
            ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml",
        ):
            text = path.read_text(encoding="utf-8")
            snippets = []
            lines = text.splitlines()
            index = 0
            while index < len(lines):
                if lines[index].strip().startswith("python - <<'PY'"):
                    index += 1
                    block = []
                    while index < len(lines) and lines[index].strip() != "PY":
                        block.append(lines[index])
                        index += 1
                    self.assertTrue(block, f"{path}: embedded block is empty")
                    snippets.append(textwrap.dedent(chr(10).join(block)))
                index += 1
            self.assertTrue(snippets, str(path))
            for number, snippet in enumerate(snippets, start=1):
                compile(snippet, f"{path}:embedded-python-{number}", "exec")

    def test_watchlist_refresh_detects_missing_catalog_candidates(self):
        for path in (
            ROOT / ".github" / "workflows" / "pc-price-monitor.yml",
            ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("missing_catalog_ids=catalog_ids - watch_ids", text)
            self.assertIn("or bool(missing_catalog_ids)", text)

    def test_watchlist_refresh_detects_catalog_url_mismatches(self):
        for path in (
            ROOT / ".github" / "workflows" / "pc-price-monitor.yml",
            ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("catalog_url_mismatch_ids", text)
            self.assertIn("or bool(catalog_url_mismatch_ids)", text)

    def test_primary_and_fast_workflows_share_current_writer_lock_without_cancelling_active_collection(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        fast = (ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml").read_text(encoding="utf-8")
        self.assertIn("group: pc-price-intelligence-writer-v3", text)
        self.assertIn("group: pc-price-intelligence-writer-v3", fast)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("cancel-in-progress: false", fast)

    def test_main_sync_is_revalidated_before_every_collection_attempt(self):
        for path in (
            ROOT / ".github" / "workflows" / "pc-price-monitor.yml",
            ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml",
        ):
            text = path.read_text(encoding="utf-8")
            reset_at = text.index("git reset --hard origin/main")
            syntax_at = text.index("python -m py_compile scripts/*.py", reset_at)
            focused_tests_at = text.index('python -m unittest discover -s tests -p "test_production_contract.py" -v', reset_at)
            regression_at = text.index('python -m unittest discover -s tests -p "test_*.py" -v', reset_at)
            monitor_at = text.index("python scripts/monitor.py", reset_at)
            self.assertLess(reset_at, syntax_at, str(path))
            self.assertLess(syntax_at, focused_tests_at, str(path))
            self.assertLess(focused_tests_at, regression_at, str(path))
            self.assertLess(regression_at, monitor_at, str(path))

    def test_monitor_limit_allows_full_discovered_watchlist(self):
        text = (ROOT / "scripts" / "monitor.py").read_text(encoding="utf-8")
        self.assertIn('MONITOR_MAX_URLS", "100"', text)

    def test_watchdog_checks_freshness_and_recovers_default_branch_failures(self):
        watchdog = (ROOT / ".github" / "workflows" / "pc-price-watchdog.yml").read_text(encoding="utf-8")
        primary = WORKFLOW.read_text(encoding="utf-8")
        # The watchdog heartbeat is intentionally every 15 minutes; the collector itself
        # still runs every 5 minutes during the provisional BF watch window.
        self.assertIn('cron: "*/15 * * * *"', watchdog)
        self.assertIn("workflow_run:", watchdog)
        self.assertIn('"PC Price Intelligence"', watchdog)
        self.assertIn('"PC Price Intelligence - Tests"', watchdog)
        self.assertIn("github.event.workflow_run.name == 'PC Price Intelligence - Tests' &&\n               github.event.workflow_run.conclusion == 'success'", watchdog)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", watchdog)
        self.assertIn("github.event.workflow_run.run_attempt == 1", watchdog)
        # A collector can conclude success yet leave stale snapshots; this is
        # still an unhealthy run and must trigger one bounded recovery.
        self.assertIn("github.event.workflow_run.conclusion == 'success'", watchdog)
        self.assertIn("!contains(github.event.workflow_run.display_title, '[watchdog-recovery]')", watchdog)
        self.assertGreaterEqual(watchdog.count("gh workflow run pc-price-monitor.yml --ref main -f watchdog_recovery=true"), 2)
        # The recovery marker is part of the run title so its completion cannot
        # trigger a recursive chain of recovery dispatches.
        self.assertIn("inputs.watchdog_recovery == true && ' [watchdog-recovery]'", primary)
        self.assertIn("watchdog_recovery:", primary)
        self.assertNotIn('cron: "12,27,42,57 * * * *"', watchdog)
        # Recovery must detect a stale writer even when a newer run is queued.
        self.assertIn("--limit 20 --json databaseId,status,conclusion,createdAt,updatedAt,headSha", watchdog)
        self.assertIn("gh run cancel", watchdog)
        # The stale-writer cutoff must be longer than the collectors' timeout.
        self.assertIn("timeout-minutes: 30", primary)
        fast = (ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml").read_text(encoding="utf-8")
        self.assertIn("timeout-minutes: 30", fast)
        self.assertIn("40*60", watchdog)
        self.assertIn("A fresh queued/running monitor remains", watchdog)

    def test_all_workflows_pin_node24_checkout_action(self):
        paths = (
            ROOT / ".github" / "workflows" / "pc-price-monitor.yml",
            ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml",
            ROOT / ".github" / "workflows" / "pc-price-tests.yml",
            ROOT / ".github" / "workflows" / "pc-price-watchdog.yml",
        )
        expected = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1"
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertIn(expected, text, str(path))
            self.assertNotIn("actions/checkout@v4", text, str(path))


    def test_known_broken_candidate_pages_use_verified_routes(self):
        catalog_path = ROOT / "config" / "candidate_catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        candidates = {item["id"]: item for item in catalog.get("candidates", [])}

        # Old GALLERIA page returned 404. The replacement is the exact current
        # ZL9R-R57T-6-B model page; its listed price is explicitly marked sold out.
        galleria = candidates["galleria-zl9r-9955hx-5070ti"]
        self.assertEqual(galleria["url"], "https://www.dospara.co.jp/TC1085/MC24569.html")
        self.assertEqual(galleria["name"], "GALLERIA ZL9R-R57T-6-B")
        self.assertEqual(galleria["ram_gb"], 32)
        self.assertEqual(galleria["ssd"], "1 TB")
        self.assertEqual(galleria["reference_price_jpy"], 738980)
        self.assertTrue(galleria["historical_sellout"])

        # Model-generation-specific official routes must not point to the old
        # G18 path or a G614-family page when the SKU is actually G615.
        self.assertEqual(
            candidates["rog-g18-2025-275hx-5070ti"]["url"],
            "https://rog.asus.com/jp/laptops/rog-strix/rog-strix-g18-2025/spec/",
        )
        self.assertEqual(
            candidates["rog-g16-2025-275hx-5070ti"]["url"],
            "https://rog.asus.com/jp/laptops/rog-strix/rog-strix-g16-2025/spec/",
        )
        self.assertEqual(
            candidates["rog-g16-8940hx-5070ti"]["url"],
            "https://rog.asus.com/jp/laptops/rog-strix/rog-strix-g16-2025-g614/spec/",
        )
        self.assertEqual(
            candidates["rog-g16-8940hx-5070ti"]["purchase_url"],
            "https://store.asus.com/jp/rog/90nr0nj7-m007r0-rog-strix-g16-2025-g614.html",
        )
        self.assertTrue(candidates["rog-g16-8940hx-5070ti"]["purchase_url_is_exact"])
        self.assertEqual(
            candidates["zephyrus-g16-386h-5070ti"]["url"],
            "https://rog.asus.com/jp/laptops/rog-zephyrus/rog-zephyrus-g16-2026/spec/",
        )

        # Never transfer a sibling G614PR price to the different 9955HX3D SKU.
        g16_9955 = candidates["rog-g16-9955hx3d"]
        self.assertEqual(g16_9955["reference_price_jpy"], 699800)
        self.assertEqual(
            g16_9955["url"],
            "https://rog.asus.com/jp/laptops/rog-strix/rog-strix-g16-2025-g614/spec/",
        )
        self.assertEqual(
            g16_9955["purchase_url"],
            "https://store.asus.com/jp/rog/90nr0nk7-m00cl0-rog-strix-g16-2025-g614.html",
        )
        self.assertTrue(g16_9955["purchase_url_is_exact"])
        self.assertFalse(g16_9955["url_is_exact"])

        # The official TUF F16 listing is a 512GB configuration, not 1TB.
        tuf_f16 = candidates["tuf-f16-14650hx-5070"]
        self.assertEqual(tuf_f16["ssd"], "512 GB")
        self.assertTrue(tuf_f16["purchase_url_is_exact"])
        self.assertNotIn("reference_price_jpy", tuf_f16)
        self.assertEqual(tuf_f16["aliases"][0], "FX608JPR-I7R32G5R5070S")

        for candidate_id in (
            "galleria-zl9r-9955hx-5070ti",
            "rog-g18-2025-275hx-5070ti",
            "rog-g16-2025-275hx-5070ti",
            "rog-g16-8940hx-5070ti",
            "zephyrus-g16-386h-5070ti",
        ):
            self.assertTrue(candidates[candidate_id]["url"].startswith("https://"))

        acer = candidates["candidate-5"]
        self.assertEqual(acer["name"], "Acer Predator Helios Neo 16 AI PHN16-I71-N93Z57T/E")
        self.assertEqual(acer["cpu"], "Core Ultra 9 290HX Plus")
        self.assertEqual(acer["reference_price_jpy"], 547800)
        self.assertEqual(acer["official_listing_reference_checked_date"], "2026-10-21")
        self.assertEqual(
            acer["url"],
            "https://www.acer.com/jp-ja/predator/laptops/helios/helios-neo-16-ai/pdp/NH.U44SJ.001",
        )
        self.assertEqual(
            acer["purchase_url"],
            "https://store.acer.com/ja-jp/acer-phn16-i71-n93z57t-e-1",
        )
        self.assertFalse(candidates["tuf-a16-8940hx-5070"]["url_is_exact"])
        self.assertTrue(candidates["tuf-a16-8940hx-5070"]["purchase_url_is_exact"])
        self.assertTrue(candidates["zephyrus-g14-386h-5070ti"]["purchase_url_is_exact"])
        self.assertNotIn("purchase_url", candidates["rog-g16-2025-275hx-5070ti"])
        self.assertNotIn("purchase_url", candidates["rog-g18-2025-275hx-5070ti"])
        self.assertEqual(candidates["candidate-4"]["monitor_page_type"], "family_landing")
        self.assertEqual(candidates["gigabyte-a18-pro-240h-5070ti"]["monitor_page_type"], "family_landing")
        self.assertEqual(
            candidates["tuf-a16-8940hx-5070"]["url"],
            "https://www.asus.com/jp/laptops/for-gaming/tuf-gaming/asus-tuf-gaming-a16-2025/techspec/",
        )
        self.assertEqual(
            candidates["tuf-f16-14650hx-5070"]["url"],
            "https://www.asus.com/jp/laptops/for-gaming/tuf-gaming/asus-tuf-gaming-f16-2025/techspec/",
        )
        self.assertEqual(
            candidates["zephyrus-g14-386h-5070ti"]["url"],
            "https://rog.asus.com/jp/laptops/rog-zephyrus/rog-zephyrus-g14-2026-gu405/spec/",
        )

if __name__ == "__main__":
    unittest.main()
