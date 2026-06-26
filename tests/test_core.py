from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import generate_trend_plots
import update_health
import update_loads
from date_utils import date_range_from_days, inclusive_dates
from intervals_icu_client import IntervalsError, get_api_key, get_athlete_id, sanitize_activity_name
from markdown_tables import read_table, render_table, write_text_atomic
from profile_paths import PROFILE_PLANS_DIR
from render_plan import resolve_plan_path, validate_plan
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

    def test_first_activity_contributes_to_new_load_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            activities = base / "activities"
            self.write_activity(activities, "2026-06-01", "70")
            rows = update_loads.calculate(base / "loads.md", activities)
            self.assertEqual(rows["2026-06-01"][1:4], ["70", "10", "2"])

    def test_existing_seed_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            loads = base / "loads.md"
            loads.write_text(
                render_table(
                    update_loads.HEADER,
                    [["2026-06-01", "50", "20", "10", "-10", "2.000"]],
                ),
                encoding="utf-8",
            )
            rows = update_loads.calculate(loads, base / "activities", date(2026, 6, 2))
            self.assertEqual(rows["2026-06-01"][2:4], ["20", "10"])
            self.assertEqual(rows["2026-06-02"][2:4], ["17", "10"])


class ConfigurationTests(unittest.TestCase):
    def test_credentials_are_required(self) -> None:
        with self.assertRaises(IntervalsError):
            get_api_key({})
        with self.assertRaises(IntervalsError):
            get_athlete_id({})

    def test_activity_names_are_safe(self) -> None:
        self.assertEqual(sanitize_activity_name("Run 🏃 / Test"), "Run - Test")

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
