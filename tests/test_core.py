from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import generate_trend_plots
import analyze_fit_files
import download_fit_files
import efficiency
import update_health
import update_efficiency
import update_loads
import update_zones
from date_utils import (
    date_range_from_days,
    expand_range_with_overlap,
    inclusive_dates,
    iso_week_id,
    monday_of_iso_week,
    previous_iso_week,
)
from intervals_icu_client import IntervalsError, get_api_key, get_athlete_id, sanitize_activity_name
from markdown_tables import read_table, render_table, write_text_atomic
from profile_paths import PROFILE_PLANS_DIR
from render_plan import latest_rendered_plan_week, resolve_plan_path, validate_plan
from validate_repo import validate_planning_readiness


class DateUtilsTests(unittest.TestCase):
    def test_inclusive_range(self) -> None:
        self.assertEqual(
            list(inclusive_dates(date(2026, 6, 1), date(2026, 6, 3))),
            [date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3)],
        )

    def test_date_range_rejects_non_positive_days(self) -> None:
        with self.assertRaises(ValueError):
            date_range_from_days(0, "2026-06-01")

    def test_overlap_expands_range_to_latest_synced_day(self) -> None:
        oldest, newest = date_range_from_days(2, "2026-06-27")
        self.assertEqual(
            expand_range_with_overlap(oldest, newest, date(2026, 6, 25)),
            (date(2026, 6, 25), date(2026, 6, 27)),
        )
        self.assertEqual(
            expand_range_with_overlap(oldest, newest, None),
            (date(2026, 6, 26), date(2026, 6, 27)),
        )

    def test_iso_week_helpers(self) -> None:
        self.assertEqual(iso_week_id(date(2026, 6, 26)), "2026-W26")
        self.assertEqual(monday_of_iso_week("2026-W27"), date(2026, 6, 29))
        self.assertEqual(previous_iso_week("2026-W01"), "2025-W52")


class MarkdownTableTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "table.md"
            text = render_table(["Datum", "Wert"], [["2026-06-01", "4"]])
            write_text_atomic(path, text)
            self.assertEqual(read_table(path), (["Datum", "Wert"], [["2026-06-01", "4"]]))

    def test_malformed_row_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "table.md"
            path.write_text("| A | B |\n|-|-|\n| only-one |\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_table(path)


class HealthCalculationTests(unittest.TestCase):
    def test_newest_health_date_detects_latest_existing_row(self) -> None:
        newest = update_health.newest_health_date(
            [
                {"2026-06-20": ["2026-06-20", "50"]},
                {"2026-06-26": ["2026-06-26", "8000"]},
            ]
        )
        self.assertEqual(newest, date(2026, 6, 26))

    def test_trimmed_weight_mean(self) -> None:
        self.assertIsNone(update_health.trimmed_weight_mean([1, 2, 3]))
        self.assertEqual(update_health.trimmed_weight_mean([1, 2, 3, 100]), 26.5)
        self.assertEqual(update_health.trimmed_weight_mean([1, 2, 3, 4, 100]), 3.0)

    def test_weight_recalculation_uses_two_decimals(self) -> None:
        rows = {
            f"2026-06-{day:02d}": [f"2026-06-{day:02d}", str(80 + day), "-", str(10 + day), "-"]
            for day in range(1, 6)
        }
        update_health.recalc_weight(rows)
        self.assertEqual(rows["2026-06-05"][2], "83.00")
        self.assertEqual(rows["2026-06-05"][4], "13.00")


class LoadCalculationTests(unittest.TestCase):
    def write_activity(self, root: Path, day: str, tss: str) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / f"{day} Test.md").write_text(f"TSS: {tss}\n", encoding="utf-8")

    def test_first_load_uses_recent_half_of_daily_tss_as_seed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            activities = base / "activities"
            for day, tss in enumerate((20, 40, 60, 80), start=1):
                self.write_activity(activities, f"2026-06-{day:02d}", str(tss))
            rows = update_loads.calculate(base / "loads.md", activities)
            self.assertEqual(rows["2026-06-01"][1:4], ["20", "70", "70"])
            self.assertEqual(rows["2026-06-02"][2:4], ["66", "69"])

    def test_existing_seed_is_replaced_when_recalculating_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            loads = base / "loads.md"
            activities = base / "activities"
            self.write_activity(activities, "2026-06-01", "70")
            loads.write_text(
                render_table(
                    update_loads.HEADER,
                    [["2026-06-01", "50", "20", "10", "-10", "2.000"]],
                ),
                encoding="utf-8",
            )
            rows = update_loads.calculate(loads, activities, date(2026, 6, 2))
            self.assertEqual(rows["2026-06-01"][2:4], ["70", "70"])
            self.assertEqual(rows["2026-06-02"][2:4], ["60", "68"])


class ZoneCalculationTests(unittest.TestCase):
    def test_zones_use_latest_threshold_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            thresholds = data_dir / "thresholds"
            thresholds.mkdir()
            (thresholds / "thresholds_swim.md").write_text(
                render_table(["Datum", "CSS / min:sec/100m"], [["2026-01-01", "1:35"]]),
                encoding="utf-8",
            )
            (thresholds / "thresholds_bike.md").write_text(
                render_table(["Datum", "FTP / W"], [["2026-01-01", "312"]]),
                encoding="utf-8",
            )
            (thresholds / "thresholds_run.md").write_text(
                render_table(
                    ["Datum", "LT / bpm", "LT / min:sec/km"],
                    [["2026-01-01", "160", "3:58"]],
                ),
                encoding="utf-8",
            )

            zones = update_zones.build_zones(data_dir)
            self.assertIn("| Z6 | Anaerobic | 171 | / | 343 | / |", zones)
            self.assertIn("| Z4 | Threshold | 152 | 166 | 4:16 | 3:51 |", zones)


class ConfigurationTests(unittest.TestCase):
    def test_credentials_are_required(self) -> None:
        with self.assertRaises(IntervalsError):
            get_api_key({})
        with self.assertRaises(IntervalsError):
            get_athlete_id({})

    def test_activity_names_are_safe(self) -> None:
        self.assertEqual(sanitize_activity_name("Run 🏃 / Test"), "Run - Test")

    def test_multisport_component_duplicates_are_expected_after_transition(self) -> None:
        self.assertTrue(
            download_fit_files.is_multisport_component_duplicate({"Swim"}, "Transition")
        )
        self.assertTrue(
            download_fit_files.is_multisport_component_duplicate(
                {"Swim", "Transition"}, "Ride"
            )
        )
        self.assertFalse(
            download_fit_files.is_multisport_component_duplicate({"Run"}, "Run")
        )

    def test_unchanged_overlap_fit_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "activity.fit"
            path.write_bytes(b"same-fit")
            self.assertTrue(download_fit_files.fit_content_is_unchanged(path, b"same-fit"))
            self.assertFalse(download_fit_files.fit_content_is_unchanged(path, b"changed-fit"))

    def test_multisport_activity_loads_are_summed(self) -> None:
        info = analyze_fit_files.FitInfo(
            Path("2026-06-21 Test Triathlon.fit"),
            {},
            {},
            [],
            [],
            datetime(2026, 6, 21, tzinfo=timezone.utc),
            "multisport",
        )
        activities = [
            {
                "start_date_local": "2026-06-21T08:00:00",
                "type": sport,
                "name": "Test Triathlon",
                "icu_training_load": load,
            }
            for sport, load in (("Swim", 20), ("Ride", 80), ("Run", 50))
        ]
        match = analyze_fit_files.match_activity(info, activities)
        self.assertIsNotNone(match)
        self.assertEqual(match["icu_training_load"], 150)

    def test_accidental_multisport_finish_restart_is_trimmed(self) -> None:
        start = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)
        restart = start + timedelta(seconds=1086)
        run_session = {
            "sport": "running",
            "start_time": start,
            "total_timer_time": 1176,
            "total_elapsed_time": 1176,
            "total_distance": 4971,
        }
        retained_lap = {
            "sport": "running",
            "start_time": start,
            "total_timer_time": 1086,
            "total_elapsed_time": 1086,
            "total_distance": 4956,
            "avg_heart_rate": 166,
            "max_heart_rate": 174,
        }
        trailing_lap = {
            "sport": "running",
            "start_time": restart,
            "total_timer_time": 90,
            "total_elapsed_time": 90,
            "total_distance": 15,
            "avg_heart_rate": 142,
            "max_heart_rate": 171,
        }
        messages = {
            "session": [
                {"sport": "swimming", "start_time": start - timedelta(minutes=45), "total_timer_time": 600},
                run_session,
            ],
            "lap": [retained_lap, trailing_lap],
            "record": [
                {"timestamp": restart - timedelta(seconds=1)},
                {"timestamp": restart + timedelta(seconds=1)},
            ],
            "event": [
                {"timestamp": restart - timedelta(seconds=1), "event_type": "stop_all"},
                {"timestamp": restart, "event_type": "start"},
                {"timestamp": restart + timedelta(seconds=90), "event_type": "stop_all"},
            ],
        }

        analyze_fit_files.trim_accidental_multisport_finish_restart(messages)

        self.assertEqual(run_session["total_timer_time"], 1086)
        self.assertEqual(run_session["total_distance"], 4956)
        self.assertEqual(messages["lap"], [retained_lap])
        self.assertEqual(len(messages["record"]), 1)

    def test_local_activity_timestamp_overrides_utc_session_start(self) -> None:
        utc_start = datetime(2026, 5, 9, 22, 48, tzinfo=timezone.utc)
        local_start = datetime(2026, 5, 10, 5, 48, tzinfo=timezone.utc)
        self.assertEqual(
            analyze_fit_files.local_activity_start(
                {"activity": [{"local_timestamp": local_start}]}, utc_start
            ),
            local_start,
        )


class EfficiencyTests(unittest.TestCase):
    def records(self, start: datetime, seconds: int, *, sport: str = "bike", stable: bool = True) -> list[dict]:
        result = []
        for second in range(seconds):
            output = 220 if stable else (180 if second % 2 else 260)
            record = {"timestamp": start + timedelta(seconds=second), "heart_rate": 130, "distance": second * 3, "enhanced_altitude": 100 + second * .01}
            if sport == "bike":
                record["power"] = output
            else:
                record["enhanced_speed"] = 3.2 if stable else (2.8 if second % 2 else 3.6)
            result.append(record)
        return result

    def test_warmup_and_post_stop_are_excluded(self) -> None:
        start = datetime(2026, 7, 1, tzinfo=timezone.utc)
        records = self.records(start, 700) + self.records(start + timedelta(seconds=800), 600)
        points = efficiency.extract_points(records, "bike")
        self.assertTrue(points)
        self.assertTrue(all(datetime.fromisoformat(point["timestamp"]) >= start + timedelta(seconds=980) for point in points))

    def test_unstable_or_missing_records_are_rejected(self) -> None:
        start = datetime(2026, 7, 1, tzinfo=timezone.utc)
        self.assertEqual(efficiency.extract_points(self.records(start, 1200, stable=False), "bike"), [])
        self.assertEqual(efficiency.extract_points([{"timestamp": start, "power": 220}], "bike"), [])

    def test_gradual_hr_rise_is_accepted_but_rapid_hr_rise_is_rejected(self) -> None:
        start = datetime(2026, 7, 1, tzinfo=timezone.utc)
        gradual = self.records(start, 1200)
        rapid = self.records(start, 1200)
        for second, record in enumerate(gradual):
            record["heart_rate"] = 125 + second / 120
        for second, record in enumerate(rapid):
            record["heart_rate"] = 125 + second / 20
        self.assertTrue(efficiency.extract_points(gradual, "bike"))
        self.assertEqual(efficiency.extract_points(rapid, "bike"), [])

    def test_first_window_after_power_transition_is_rejected(self) -> None:
        start = datetime(2026, 7, 1, tzinfo=timezone.utc)
        records = self.records(start, 1200)
        for second, record in enumerate(records):
            record["power"] = 150 if second < 700 else 300
        points = efficiency.extract_points(records, "bike")
        self.assertTrue(points)
        self.assertTrue(all(datetime.fromisoformat(point["timestamp"]) >= start + timedelta(seconds=900) for point in points))

    def test_short_upper_interval_can_contribute_after_settling(self) -> None:
        start = datetime(2026, 7, 1, tzinfo=timezone.utc)
        records = self.records(start, 1200)
        for second, record in enumerate(records):
            if 700 <= second < 1000:
                record["power"] = 300
                record["heart_rate"] = 150
            else:
                record["power"] = 150
                record["heart_rate"] = 130
        points = efficiency.extract_points(records, "bike")
        self.assertTrue(any(datetime.fromisoformat(point["timestamp"]) == start + timedelta(seconds=810) for point in points))

    def test_run_gap_uses_grade_and_falls_back_to_pace(self) -> None:
        start = datetime(2026, 7, 1, tzinfo=timezone.utc)
        hilly = efficiency.extract_points(self.records(start, 1200, sport="run"), "run")
        flat = self.records(start, 1200, sport="run")
        for record in flat:
            record.pop("enhanced_altitude")
        fallback = efficiency.extract_points(flat, "run")
        self.assertTrue(hilly and fallback)
        self.assertEqual(fallback[0]["gap_method"], "pace_fallback")
        self.assertNotEqual(hilly[0]["gap_speed_mps"], fallback[0]["gap_speed_mps"])

    def test_coverage_and_week_replacement(self) -> None:
        points = []
        for activity in range(5):
            for hr in (124, 128, 132, 136):
                points.append({"hr": hr, "output": 2 * hr, "activity": f"a{activity}"})
        result = update_efficiency.calculate(points)
        self.assertEqual(result["status"], "vorläufig")
        for activity in range(5):
            for hr in (149, 153, 157, 161):
                points.append({"hr": hr, "output": 2 * hr, "activity": f"b{activity}"})
        result = update_efficiency.calculate(points)
        self.assertEqual(result["status"], "robust")
        self.assertIsNotNone(result["values"][130])
        self.assertIsNotNone(result["values"][155])
        self.assertIsNotNone(result["intervals"][130])
        self.assertIsNotNone(result["intervals"][155])
        rows = update_efficiency.upsert([["2026-W31", "bike", "old"]], [["2026-W31", "bike", "new"]])
        self.assertEqual(rows, [["2026-W31", "bike", "new"]])

    def test_efficiency_history_uses_iso_week_labels(self) -> None:
        self.assertEqual(generate_trend_plots.iso_week_label(date(2026, 7, 20)), "W30")
        self.assertEqual(generate_trend_plots.iso_week_label(date(2026, 7, 27)), "W31")
        self.assertEqual(
            generate_trend_plots.efficiency_history_window(date(2026, 7, 27)),
            (date(2026, 5, 4), date(2026, 7, 27)),
        )

    def test_hr_drift_ignores_initial_sensor_dropout(self) -> None:
        start = datetime(2026, 7, 10, tzinfo=timezone.utc)
        points = []
        for second in range(1000):
            heart_rate = 70 if second < 100 else 130
            points.append((start + timedelta(seconds=second), heart_rate, 3.0))
        self.assertEqual(analyze_fit_files.hr_drift_from_points(points), "0.0% (stabil)")

    def test_demo_profile_is_not_planning_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            (data_dir / "athlete-profile.md").write_text(
                "| Name | DEMO |\n| FTP | -1W |\n",
                encoding="utf-8",
            )
            errors = validate_planning_readiness(data_dir)
            self.assertEqual(len(errors), 1)
            self.assertIn("DEMO", errors[0])
            self.assertIn("-1", errors[0])


class PlanTests(unittest.TestCase):
    def test_all_active_profile_plans_validate(self) -> None:
        for path in PROFILE_PLANS_DIR.glob("*.json"):
            with self.subTest(path=path.name):
                validate_plan(json.loads(path.read_text(encoding="utf-8-sig")))

    def test_unknown_plan_keys_are_rejected(self) -> None:
        plan = {
            "schema_version": 1,
            "week": "2026-W23",
            "days": [{"date": "2026-06-01", "sessions": []}],
            "unexpected": True,
        }
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_plan_must_belong_to_active_profile(self) -> None:
        other = ROOT / "profiles" / "__other__" / "plans" / "plan.json"
        with self.assertRaises(ValueError):
            resolve_plan_path(str(other))

    def test_latest_rendered_plan_week_uses_week_identifier_not_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plans = Path(directory)
            (plans / "2026-W28.html").write_text("old", encoding="utf-8")
            (plans / "2026-W29.html").write_text("new", encoding="utf-8")
            (plans / "notes.html").write_text("ignore", encoding="utf-8")
            self.assertEqual(latest_rendered_plan_week(plans), "2026-W29")


class TrendPlotTests(unittest.TestCase):
    def test_body_fat_columns_are_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            table = Path(directory) / "weight.md"
            table.write_text(
                render_table(
                    [
                        "Datum",
                        "Gewicht / kg",
                        "7-Tage-Mittel-Gewicht / kg",
                        "Körperfettanteil / %",
                        "7-Tage-Mittel-Körperfettanteil / %",
                    ],
                    [["2026-06-01", "80", "80.00", "15", "15.00"]],
                ),
                encoding="utf-8",
            )
            daily = generate_trend_plots.points_from_table(table, "Körperfettanteil / %")
            trend = generate_trend_plots.points_from_table(
                table, "7-Tage-Mittel-Körperfettanteil / %"
            )
            self.assertEqual(daily[0].value, 15.0)
            self.assertEqual(trend[0].value, 15.0)

    def test_calories_plot_replaces_steps_when_table_exists(self) -> None:
        original_data_dir = generate_trend_plots.DATA_DIR
        try:
            with tempfile.TemporaryDirectory() as directory:
                data_dir = Path(directory)
                health_dir = data_dir / "health"
                health_dir.mkdir()
                generate_trend_plots.DATA_DIR = data_dir

                self.assertIn("body_steps.svg", generate_trend_plots.trend_section_html("2026-W26"))
                self.assertNotIn("body_calories.svg", generate_trend_plots.trend_section_html("2026-W26"))
                self.assertIn("efficiency_weekly.svg", generate_trend_plots.trend_section_html("2026-W26"))
                self.assertIn("efficiency_bike.svg", generate_trend_plots.trend_section_html("2026-W26"))
                self.assertIn("efficiency_run.svg", generate_trend_plots.trend_section_html("2026-W26"))

                (health_dir / "calories.md").write_text(
                    render_table(
                        ["Datum", "Ruhe-Kalorien", "Aktiv-Kalorien"],
                        [["2026-06-25", "2266", "1155"]],
                    ),
                    encoding="utf-8",
                )
                html = generate_trend_plots.trend_section_html("2026-W26")
                self.assertIn("body_calories.svg", html)
                self.assertNotIn("body_steps.svg", html)
        finally:
            generate_trend_plots.DATA_DIR = original_data_dir


if __name__ == "__main__":
    unittest.main()
