"""Tests for source-preserving Excel import."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook, load_workbook

from app.database.connection import connect_database
from app.importers.excel_importer import import_excel
from app.gamification.progression import calculate_progression, parse_level_definitions
from app.models.roadmap import ProgressUpdate
from app.services.gamification_service import get_gamification_data, sync_xp_awards
from app.services.roadmap_service import (
    clear_item_progress,
    get_dashboard_data,
    get_roadmap_item,
    get_roadmap_items,
    save_item_progress,
)


class ExcelImporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.root = Path(self.temp_dir.name)
        self.workbook_path = self.root / "source.xlsx"
        self.database_path = self.root / "roadmap.sqlite3"
        self._make_workbook()
        self.connection = connect_database(self.database_path)

    def tearDown(self) -> None:
        self.connection.close()
        self.temp_dir.cleanup()

    def _make_workbook(self) -> None:
        workbook = Workbook()
        dashboard = workbook.active
        dashboard.title = "Dashboard"
        dashboard["B4"] = "Local Test Profile"
        dashboard["E8"] = "=SUM(Roadmap!H2:H63)"
        dashboard["E9"] = 1
        dashboard["C15"] = "IT Apprentice"
        for column, value in enumerate(("Level", "XP Band", "Title", "Unlock", "Reward"), 1):
            dashboard.cell(14, column, value)
        for row, values in enumerate((
            (1, "0-99", "IT Apprentice", "Start", "Build homelab"),
            (2, "100-199", "Network Scout", "100 XP", "Network+"),
            (3, "200+", "Security Practitioner", "200 XP", "Capstone"),
        ), 15):
            for column, value in enumerate(values, 1):
                dashboard.cell(row, column, value)

        roadmap = workbook.create_sheet("Roadmap")
        roadmap.append(["Month", "Age", "Year", "Track", "Focus", "Monthly Mission", "Status", "XP", "Done?", "Notes"])
        roadmap.append(["2026-09", "19", "Year 1", "Foundation", "Network+ / Linux / Git", "Build a lab", "Not Started", 0, "No", "source note"])

        skills = workbook.create_sheet("Skill Matrix")
        skills.append(["Skill", "Track", "Target Age", "What Good Looks Like", "Status", "XP Value"])
        skills.append(["Networking", "Foundation", "20", "TCP/IP", "Not Started", 500])
        certs = workbook.create_sheet("Certifications")
        certs.append(["Certification", "Status", "Domain", "Target Age", "Target Window", "Priority"])
        certs.append(["CompTIA A+", "Completed", "IT Foundations", "19", "Completed", "Done"])
        projects = workbook.create_sheet("Projects")
        projects.append(["ID", "Project", "Track", "Definition of Done", "Target", "XP", "Status"])
        projects.append(["P01", "Homelab v1", "Foundation", "AD + Windows + Linux", "Year 1", 100, "Not Started"])

        starter = workbook.create_sheet("12-Month Starter")
        starter["C5"] = "=IF(B5=0,0,C5/B5)"
        workbook.create_sheet("Microsoft Track")
        wallet = workbook.create_sheet("My Certifications")
        wallet["A25"] = "Cisco CCNA"
        wallet["F25"] = "Planned"
        workbook.create_sheet("Scripting & Dev")
        workbook.create_sheet("Beyond 25")
        workbook.create_sheet("Weekly Tracker")
        workbook.create_sheet("GitHub Portfolio")
        workbook.create_sheet("Resources")
        workbook.create_sheet("Lists")
        workbook.save(self.workbook_path)

    def test_import_persists_source_rows_cells_and_formulas(self) -> None:
        result = import_excel(self.connection, self.workbook_path)

        self.assertEqual(result.sheet_count, 14)
        self.assertGreater(result.source_cell_count, 20)
        self.assertEqual(result.formula_count, 2)
        formula = self.connection.execute(
            "SELECT formula_text FROM source_cells WHERE sheet_name='12-Month Starter' AND coordinate='C5'"
        ).fetchone()[0]
        self.assertEqual(formula, "=IF(B5=0,0,C5/B5)")
        source_note = self.connection.execute(
            "SELECT values_json FROM source_rows WHERE sheet_name='Roadmap' AND row_number=2"
        ).fetchone()[0]
        self.assertIn("source note", source_note)
        self.assertTrue(any(issue.code == "FORMULA_CIRCULAR_REFERENCE" for issue in result.issues))

    def test_normalized_item_keeps_status_and_source_reward(self) -> None:
        import_excel(self.connection, self.workbook_path)
        row = self.connection.execute(
            "SELECT name, status, xp_reward, category, target_period FROM roadmap_items WHERE item_type='monthly_mission'"
        ).fetchone()
        self.assertEqual(tuple(row), ("Network+ / Linux / Git", "Not Started", 100, "Foundation", "2026-09"))

    def test_reimport_of_identical_workbook_is_idempotent(self) -> None:
        first = import_excel(self.connection, self.workbook_path)
        second = import_excel(self.connection, self.workbook_path)
        self.assertFalse(first.already_imported)
        self.assertTrue(second.already_imported)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM workbooks").fetchone()[0], 1)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM roadmap_items").fetchone()[0], 5)

    def test_changed_workbook_creates_a_distinct_snapshot(self) -> None:
        first = import_excel(self.connection, self.workbook_path)
        workbook = load_workbook(self.workbook_path)
        workbook["Roadmap"]["A2"] = "2026-10"
        workbook.save(self.workbook_path)

        second = import_excel(self.connection, self.workbook_path)
        self.assertNotEqual(first.workbook_id, second.workbook_id)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM workbooks").fetchone()[0], 2)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM roadmap_items").fetchone()[0], 10)

    def test_progress_is_local_and_does_not_replace_source_status(self) -> None:
        import_excel(self.connection, self.workbook_path)
        mission = get_roadmap_items(self.connection, item_type="monthly_mission")[0]

        save_item_progress(
            self.connection,
            mission["item_id"],
            ProgressUpdate(
                status="In progress",
                progress_percent=45,
                date_started="2026-10-31",
                note="Local note, separate from the workbook.",
            ),
        )
        updated = get_roadmap_item(self.connection, mission["item_id"])
        self.assertEqual(updated["status"], "Not Started")
        self.assertEqual(updated["progress_status"], "In progress")
        self.assertEqual(updated["progress_percent"], 45)
        self.assertEqual(updated["progress_date_started"], "2026-10-31")
        self.assertEqual(updated["progress_note"], "Local note, separate from the workbook.")
        source_status = self.connection.execute(
            "SELECT value_json FROM source_cells WHERE sheet_name='Roadmap' AND coordinate='G2'"
        ).fetchone()[0]
        self.assertEqual(source_status, '"Not Started"')
        dashboard = get_dashboard_data(self.connection)
        self.assertEqual(dashboard["roadmap_in_progress"], 1)
        self.assertEqual(dashboard["roadmap_completed"], 0)
        self.assertTrue(import_excel(self.connection, self.workbook_path).already_imported)
        self.assertEqual(get_roadmap_item(self.connection, mission["item_id"])["progress_percent"], 45)

        save_item_progress(
            self.connection,
            mission["item_id"],
            ProgressUpdate(
                status="Completed",
                progress_percent=100,
                date_started="2026-10-31",
                date_completed="2026-11-03",
            ),
        )
        dashboard = get_dashboard_data(self.connection)
        self.assertEqual(dashboard["roadmap_completed"], 1)
        self.assertEqual(dashboard["roadmap_percent"], 100)
        self.assertIsNone(dashboard["current_mission"])

    def test_progress_validation_and_reset(self) -> None:
        import_excel(self.connection, self.workbook_path)
        mission = get_roadmap_items(self.connection, item_type="monthly_mission")[0]
        with self.assertRaisesRegex(ValueError, "100%"):
            save_item_progress(
                self.connection,
                mission["item_id"],
                ProgressUpdate(status="Completed", progress_percent=80),
            )
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            save_item_progress(
                self.connection,
                mission["item_id"],
                ProgressUpdate(status="In progress", progress_percent=20, date_started="2026-2-1"),
            )
        with self.assertRaisesRegex(ValueError, "earlier than"):
            save_item_progress(
                self.connection,
                mission["item_id"],
                ProgressUpdate(
                    status="Completed", progress_percent=100,
                    date_started="2026-11-03", date_completed="2026-11-02",
                ),
            )

        save_item_progress(
            self.connection,
            mission["item_id"],
            ProgressUpdate(status="Blocked", progress_percent=20, note="Waiting on lab access."),
        )
        clear_item_progress(self.connection, mission["item_id"])
        reset = get_roadmap_item(self.connection, mission["item_id"])
        self.assertEqual(reset["progress_status"], "Not started")
        self.assertEqual(reset["progress_percent"], 0)
        self.assertFalse(reset["has_progress_override"])

    def test_progression_uses_source_levels_and_caps_at_last_level(self) -> None:
        import_excel(self.connection, self.workbook_path)
        levels = parse_level_definitions({
            "A14": "Level", "B14": "XP Band", "C14": "Title", "D14": "Unlock", "E14": "Reward",
            "A15": 1, "B15": "0–499", "C15": "IT Apprentice", "D15": "Start", "E15": "Build homelab",
            "A16": 2, "B16": "500–999", "C16": "Network Scout", "D16": "500 XP", "E16": "Network+",
            "A17": 10, "B17": "5,000+", "C17": "Cybersecurity Practitioner", "D17": "5,000 XP", "E17": "Final capstone",
        })
        self.assertEqual([level.level for level in levels], [1, 2, 10])
        at_level_two = calculate_progression(500, levels)
        self.assertEqual(at_level_two["current_level"], 2)
        self.assertEqual(at_level_two["level_title"], "Network Scout")
        at_max = calculate_progression(10_000, levels)
        self.assertEqual(at_max["current_level"], 10)
        self.assertTrue(at_max["is_max_level"])
        self.assertEqual(at_max["next_level_reward"], "")

    def test_source_rewards_award_once_reversal_and_recompletion(self) -> None:
        import_excel(self.connection, self.workbook_path)
        mission = get_roadmap_items(self.connection, item_type="monthly_mission")[0]
        skill = get_roadmap_items(self.connection, item_type="skill")[0]
        project = get_roadmap_items(self.connection, item_type="project")[0]

        initial = get_gamification_data(self.connection)
        self.assertEqual((initial["career_xp"], initial["track_xp"]), (0, 0))
        self.assertEqual(initial["current_level"], 1)

        update_completed = ProgressUpdate(status="Completed", progress_percent=100)
        save_item_progress(self.connection, mission["item_id"], update_completed)
        save_item_progress(self.connection, skill["item_id"], update_completed)
        save_item_progress(self.connection, project["item_id"], update_completed)
        self.assertEqual(sync_xp_awards(self.connection), 0)

        earned = get_gamification_data(self.connection)
        self.assertEqual(earned["career_xp"], 200)
        self.assertEqual(earned["track_xp"], 500)
        self.assertEqual(earned["total_xp"], 700)
        self.assertEqual(earned["current_level"], 3)
        self.assertEqual(earned["awarded_items"], 3)
        self.assertEqual(earned["completed_reward_items"], 3)
        self.assertEqual(earned["xp_available"], 0)

        clear_item_progress(self.connection, mission["item_id"])
        reset = get_gamification_data(self.connection)
        self.assertEqual(reset["career_xp"], 100)
        self.assertEqual(reset["current_level"], 2)
        self.assertEqual(reset["awarded_items"], 2)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM xp_transactions WHERE item_id=?", (mission["item_id"],)
            ).fetchone()[0],
            2,
        )

        save_item_progress(self.connection, mission["item_id"], update_completed)
        restored = get_gamification_data(self.connection)
        self.assertEqual(restored["career_xp"], 200)
        self.assertEqual(restored["total_xp"], 700)
        self.assertEqual(restored["awarded_items"], 3)

    def test_imported_source_completion_awards_without_local_override(self) -> None:
        workbook = load_workbook(self.workbook_path)
        workbook["Projects"]["G2"] = "Done"
        workbook.save(self.workbook_path)
        import_excel(self.connection, self.workbook_path)

        self.assertEqual(sync_xp_awards(self.connection), 1)
        project = get_roadmap_items(self.connection, item_type="project")[0]
        self.assertEqual(project["status"], "Done")
        self.assertEqual(project["progress_status"], "Completed")
        self.assertEqual(project["xp_awarded"], 100)
        data = get_gamification_data(self.connection)
        self.assertEqual(data["career_xp"], 100)
        self.assertEqual(data["current_level"], 2)
        self.assertEqual(sync_xp_awards(self.connection), 0)

    def test_search_filters_and_year_sort_use_source_fields(self) -> None:
        import_excel(self.connection, self.workbook_path)
        search = get_roadmap_items(self.connection, query="linux")
        self.assertEqual(
            {item["name"] for item in search},
            {"Network+ / Linux / Git", "Homelab v1"},
        )
        skills = get_roadmap_items(
            self.connection,
            item_type="skill",
            category="Foundation",
            sort_by="Phase",
        )
        self.assertEqual([item["name"] for item in skills], ["Networking"])
        completed_source = get_roadmap_items(self.connection, source_status="Completed")
        self.assertIn("CompTIA A+", [item["name"] for item in completed_source])
        year_items = get_roadmap_items(self.connection, year="2026", sort_by="Year")
        self.assertEqual([item["name"] for item in year_items], ["Network+ / Linux / Git"])
        self.assertEqual(get_roadmap_items(self.connection, query="%"), [])

    def test_v1_database_upgrade_preserves_imported_rows(self) -> None:
        import_excel(self.connection, self.workbook_path)
        item_count = self.connection.execute("SELECT COUNT(*) FROM roadmap_items").fetchone()[0]
        source_count = self.connection.execute("SELECT COUNT(*) FROM source_cells").fetchone()[0]
        self.connection.execute("DROP TABLE roadmap_progress")
        self.connection.execute("DROP TABLE xp_transactions")
        self.connection.execute("DELETE FROM schema_migrations WHERE version IN (2, 3)")
        self.connection.commit()
        self.connection.close()

        self.connection = connect_database(self.database_path)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM roadmap_items").fetchone()[0], item_count)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM source_cells").fetchone()[0], source_count)
        self.assertEqual(
            self.connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0], 3
        )
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='roadmap_progress'").fetchone()[0],
            1,
        )
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='xp_transactions'").fetchone()[0],
            1,
        )


if __name__ == "__main__":
    unittest.main()
